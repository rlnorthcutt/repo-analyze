import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from repo_analyze import analyzer
from repo_analyze.analyzer import _strip_fences


class TestStripFences:
    def test_no_fences_unchanged(self):
        text = '{"key": "value"}'
        assert _strip_fences(text) == text

    def test_strips_json_fence(self):
        text = '```json\n{"key": "value"}\n```'
        assert _strip_fences(text) == '{"key": "value"}'

    def test_strips_plain_fence(self):
        text = '```\n{"key": "value"}\n```'
        assert _strip_fences(text) == '{"key": "value"}'

    def test_strips_surrounding_whitespace(self):
        text = '  {"key": "value"}  '
        assert _strip_fences(text) == '{"key": "value"}'

    def test_strips_fence_with_trailing_whitespace(self):
        text = '```json\n{"a": 1}\n```\n'
        assert _strip_fences(text) == '{"a": 1}'

    def test_multiline_json(self):
        text = '```json\n{\n  "a": 1,\n  "b": 2\n}\n```'
        result = _strip_fences(text)
        assert json.loads(result) == {"a": 1, "b": 2}


def _make_mock_response(text: str) -> MagicMock:
    """Build a mock anthropic response with the given text."""
    response = MagicMock()
    response.content = [MagicMock(text=text)]
    return response


class TestAnalyzeFile:
    def test_returns_required_keys(self, tmp_path):
        test_file = tmp_path / "main.py"
        test_file.write_text("print('hello')", encoding="utf-8")

        payload = {
            "path": "main.py",
            "role": "entrypoint",
            "summary": "A hello world script.",
            "suggestions": [],
        }

        with patch("repo_analyze.analyzer.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _make_mock_response(
                json.dumps(payload)
            )
            result = analyzer.analyze_file(test_file, tmp_path)

        assert result["path"] == "main.py"
        assert result["role"] == "entrypoint"
        assert "summary" in result
        assert "suggestions" in result

    def test_path_is_canonical(self, tmp_path):
        """path in result always matches the relative path, not what Claude returns."""
        sub = tmp_path / "src"
        sub.mkdir()
        test_file = sub / "core.py"
        test_file.write_text("x = 1", encoding="utf-8")

        payload = {
            "path": "WRONG_PATH.py",  # Claude might return wrong path
            "role": "core",
            "summary": "Core module.",
            "suggestions": [],
        }

        with patch("repo_analyze.analyzer.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _make_mock_response(
                json.dumps(payload)
            )
            result = analyzer.analyze_file(test_file, tmp_path)

        assert result["path"] == "src/core.py"

    def test_strips_fences_from_response(self, tmp_path):
        test_file = tmp_path / "app.py"
        test_file.write_text("x = 1", encoding="utf-8")

        payload = {"path": "app.py", "role": "core", "summary": "App.", "suggestions": []}
        fenced = f"```json\n{json.dumps(payload)}\n```"

        with patch("repo_analyze.analyzer.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _make_mock_response(fenced)
            result = analyzer.analyze_file(test_file, tmp_path)

        assert result["role"] == "core"

    def test_truncates_large_files(self, tmp_path):
        test_file = tmp_path / "big.py"
        test_file.write_text("x" * 20_000, encoding="utf-8")

        payload = {"path": "big.py", "role": "other", "summary": "Big file.", "suggestions": []}

        with patch("repo_analyze.analyzer.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _make_mock_response(
                json.dumps(payload)
            )
            analyzer.analyze_file(test_file, tmp_path)

            call_args = MockClient.return_value.messages.create.call_args
            prompt = call_args[1]["messages"][0]["content"]
            assert "[truncated]" in prompt

    def test_raises_on_invalid_json(self, tmp_path):
        test_file = tmp_path / "app.py"
        test_file.write_text("x = 1", encoding="utf-8")

        with patch("repo_analyze.analyzer.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _make_mock_response(
                "not json at all"
            )
            with pytest.raises(json.JSONDecodeError):
                analyzer.analyze_file(test_file, tmp_path)


class TestSelectKeyFiles:
    def test_returns_subset_of_files(self, tmp_path):
        files = []
        for name in ["main.py", "utils.py", "test_main.py", "README.md"]:
            f = tmp_path / name
            f.write_text("x", encoding="utf-8")
            files.append(f)

        payload = {"files": ["main.py", "README.md"]}

        with patch("repo_analyze.analyzer.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _make_mock_response(
                json.dumps(payload)
            )
            result = analyzer.select_key_files(files, tmp_path, "tree")

        assert len(result) == 2
        names = {f.name for f in result}
        assert names == {"main.py", "README.md"}

    def test_returns_path_objects(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("x", encoding="utf-8")
        payload = {"files": ["main.py"]}

        with patch("repo_analyze.analyzer.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _make_mock_response(
                json.dumps(payload)
            )
            result = analyzer.select_key_files([f], tmp_path, "tree")

        assert all(isinstance(p, Path) for p in result)

    def test_unknown_files_excluded(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("x", encoding="utf-8")
        # Claude returns a file that doesn't exist in our list
        payload = {"files": ["nonexistent.py"]}

        with patch("repo_analyze.analyzer.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _make_mock_response(
                json.dumps(payload)
            )
            result = analyzer.select_key_files([f], tmp_path, "tree")

        assert result == []

    def test_raises_on_api_error(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("x", encoding="utf-8")

        with patch("repo_analyze.analyzer.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = RuntimeError("API error")
            with pytest.raises(RuntimeError):
                analyzer.select_key_files([f], tmp_path, "tree")


class TestGenerateExecutiveSummary:
    def test_returns_string(self, tmp_path):
        file_analyses = [
            {"path": "main.py", "role": "entrypoint", "summary": "Entry point.", "suggestions": []}
        ]
        stats = {"total_files": 1, "total_lines": 10, "languages": {"Python": {"files": 1, "lines": 10}}}

        with patch("repo_analyze.analyzer.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _make_mock_response(
                "## Overview\n\nThis project does X."
            )
            result = analyzer.generate_executive_summary(file_analyses, stats, "tree/")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_analyses(self):
        stats = {"total_files": 0, "total_lines": 0, "languages": {}}

        with patch("repo_analyze.analyzer.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _make_mock_response(
                "Empty project."
            )
            result = analyzer.generate_executive_summary([], stats, "tree/")

        assert isinstance(result, str)


class TestGenerateClaudeMd:
    def test_returns_string(self):
        file_analyses = [
            {"path": "main.py", "role": "entrypoint", "summary": "Entry.", "suggestions": []}
        ]
        stats = {"total_files": 1, "total_lines": 5, "languages": {}}

        with patch("repo_analyze.analyzer.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _make_mock_response(
                "# CLAUDE.md\n\nProject info here."
            )
            result = analyzer.generate_claude_md(file_analyses, stats, "tree/")

        assert isinstance(result, str)

    def test_limits_suggestions_sent_to_api(self):
        """Only the first 20 suggestions should be included in the prompt."""
        file_analyses = [
            {
                "path": f"file{i}.py",
                "role": "other",
                "summary": "A file.",
                "suggestions": [
                    {"type": "improvement", "description": f"Suggestion {i}"}
                    for i in range(5)
                ],
            }
            for i in range(10)  # 10 files × 5 suggestions = 50 total
        ]
        stats = {"total_files": 10, "total_lines": 100, "languages": {}}

        with patch("repo_analyze.analyzer.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _make_mock_response(
                "# CLAUDE.md"
            )
            analyzer.generate_claude_md(file_analyses, stats, "tree/")

            call_args = MockClient.return_value.messages.create.call_args
            prompt = call_args[1]["messages"][0]["content"]

        # Count suggestion lines in the prompt — should be at most 20
        suggestion_lines = [l for l in prompt.splitlines() if l.startswith("- [")]
        assert len(suggestion_lines) <= 20
