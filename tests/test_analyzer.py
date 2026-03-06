import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import anthropic
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


class TestCallClaude:
    def test_uses_sdk_when_api_key_set(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="sdk response")]

        with patch("repo_analyze.analyzer._has_api_key", return_value=True):
            with patch("repo_analyze.analyzer.anthropic.Anthropic") as MockClient:
                MockClient.return_value.messages.create.return_value = mock_response
                result = analyzer._call_claude("test prompt")

        assert result == "sdk response"
        MockClient.return_value.messages.create.assert_called_once()

    def test_uses_cli_when_no_api_key_but_cli_available(self):
        mock_result = MagicMock()
        mock_result.stdout = "cli response"

        with patch("repo_analyze.analyzer._has_api_key", return_value=False):
            with patch("repo_analyze.analyzer._has_claude_cli", return_value=True):
                with patch("repo_analyze.analyzer.subprocess.run", return_value=mock_result) as mock_run:
                    result = analyzer._call_claude("test prompt")

        assert result == "cli response"
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "claude"
        assert "-p" in call_args
        assert "test prompt" in call_args

    def test_cli_receives_exact_prompt(self):
        mock_result = MagicMock()
        mock_result.stdout = "response"

        with patch("repo_analyze.analyzer._has_api_key", return_value=False):
            with patch("repo_analyze.analyzer._has_claude_cli", return_value=True):
                with patch("repo_analyze.analyzer.subprocess.run", return_value=mock_result) as mock_run:
                    analyzer._call_claude("my specific prompt")

        cmd = mock_run.call_args[0][0]
        assert "my specific prompt" in cmd

    def test_raises_when_no_backend_available(self):
        with patch("repo_analyze.analyzer._has_api_key", return_value=False):
            with patch("repo_analyze.analyzer._has_claude_cli", return_value=False):
                with pytest.raises(RuntimeError, match="No Claude backend available"):
                    analyzer._call_claude("test prompt")

    def test_api_key_takes_priority_over_cli(self):
        """SDK is used even when CLI is also available, if API key is set."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="sdk wins")]

        with patch("repo_analyze.analyzer._has_api_key", return_value=True):
            with patch("repo_analyze.analyzer._has_claude_cli", return_value=True):
                with patch("repo_analyze.analyzer.anthropic.Anthropic") as MockClient:
                    with patch("repo_analyze.analyzer.subprocess.run") as mock_run:
                        MockClient.return_value.messages.create.return_value = mock_response
                        result = analyzer._call_claude("prompt")

        assert result == "sdk wins"
        mock_run.assert_not_called()

    def test_sdk_passes_max_tokens(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="response")]

        with patch("repo_analyze.analyzer._has_api_key", return_value=True):
            with patch("repo_analyze.analyzer.anthropic.Anthropic") as MockClient:
                MockClient.return_value.messages.create.return_value = mock_response
                analyzer._call_claude("prompt", max_tokens=2048)

        call_kwargs = MockClient.return_value.messages.create.call_args[1]
        assert call_kwargs["max_tokens"] == 2048

    def test_cli_error_propagates(self):
        with patch("repo_analyze.analyzer._has_api_key", return_value=False):
            with patch("repo_analyze.analyzer._has_claude_cli", return_value=True):
                with patch(
                    "repo_analyze.analyzer.subprocess.run",
                    side_effect=subprocess.CalledProcessError(1, "claude"),
                ):
                    with pytest.raises(subprocess.CalledProcessError):
                        analyzer._call_claude("prompt")

    def test_falls_back_to_cli_on_invalid_api_key(self):
        """An invalid API key (401) should transparently fall back to the Claude CLI."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        auth_error = anthropic.AuthenticationError(
            "invalid x-api-key", response=mock_response, body={}
        )
        mock_cli_result = MagicMock()
        mock_cli_result.stdout = "cli response"

        with patch("repo_analyze.analyzer._has_api_key", return_value=True):
            with patch("repo_analyze.analyzer.anthropic.Anthropic") as MockClient:
                MockClient.return_value.messages.create.side_effect = auth_error
                with patch("repo_analyze.analyzer._has_claude_cli", return_value=True):
                    with patch(
                        "repo_analyze.analyzer.subprocess.run", return_value=mock_cli_result
                    ) as mock_run:
                        result = analyzer._call_claude("prompt")

        assert result == "cli response"
        mock_run.assert_called_once()

    def test_raises_clear_error_when_key_invalid_and_no_cli(self):
        """If the API key is invalid and no CLI is available, raise a helpful error."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        auth_error = anthropic.AuthenticationError(
            "invalid x-api-key", response=mock_response, body={}
        )

        with patch("repo_analyze.analyzer._has_api_key", return_value=True):
            with patch("repo_analyze.analyzer.anthropic.Anthropic") as MockClient:
                MockClient.return_value.messages.create.side_effect = auth_error
                with patch("repo_analyze.analyzer._has_claude_cli", return_value=False):
                    with pytest.raises(RuntimeError, match="authentication failed"):
                        analyzer._call_claude("prompt")


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

        with patch("repo_analyze.analyzer._call_claude", return_value=json.dumps(payload)):
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

        with patch("repo_analyze.analyzer._call_claude", return_value=json.dumps(payload)):
            result = analyzer.analyze_file(test_file, tmp_path)

        assert result["path"] == "src/core.py"

    def test_strips_fences_from_response(self, tmp_path):
        test_file = tmp_path / "app.py"
        test_file.write_text("x = 1", encoding="utf-8")

        payload = {"path": "app.py", "role": "core", "summary": "App.", "suggestions": []}
        fenced = f"```json\n{json.dumps(payload)}\n```"

        with patch("repo_analyze.analyzer._call_claude", return_value=fenced):
            result = analyzer.analyze_file(test_file, tmp_path)

        assert result["role"] == "core"

    def test_truncates_large_files(self, tmp_path):
        test_file = tmp_path / "big.py"
        test_file.write_text("x" * 20_000, encoding="utf-8")

        payload = {"path": "big.py", "role": "other", "summary": "Big file.", "suggestions": []}

        with patch("repo_analyze.analyzer._call_claude", return_value=json.dumps(payload)) as mock_call:
            analyzer.analyze_file(test_file, tmp_path)

        prompt_sent = mock_call.call_args[0][0]
        assert "[truncated]" in prompt_sent

    def test_raises_on_invalid_json(self, tmp_path):
        test_file = tmp_path / "app.py"
        test_file.write_text("x = 1", encoding="utf-8")

        with patch("repo_analyze.analyzer._call_claude", return_value="not json at all"):
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

        with patch("repo_analyze.analyzer._call_claude", return_value=json.dumps(payload)):
            result = analyzer.select_key_files(files, tmp_path, "tree")

        assert len(result) == 2
        names = {f.name for f in result}
        assert names == {"main.py", "README.md"}

    def test_returns_path_objects(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("x", encoding="utf-8")
        payload = {"files": ["main.py"]}

        with patch("repo_analyze.analyzer._call_claude", return_value=json.dumps(payload)):
            result = analyzer.select_key_files([f], tmp_path, "tree")

        assert all(isinstance(p, Path) for p in result)

    def test_unknown_files_excluded(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("x", encoding="utf-8")
        payload = {"files": ["nonexistent.py"]}

        with patch("repo_analyze.analyzer._call_claude", return_value=json.dumps(payload)):
            result = analyzer.select_key_files([f], tmp_path, "tree")

        assert result == []

    def test_raises_on_backend_error(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("x", encoding="utf-8")

        with patch("repo_analyze.analyzer._call_claude", side_effect=RuntimeError("API error")):
            with pytest.raises(RuntimeError):
                analyzer.select_key_files([f], tmp_path, "tree")


class TestGenerateExecutiveSummary:
    def test_returns_string(self):
        file_analyses = [
            {"path": "main.py", "role": "entrypoint", "summary": "Entry point.", "suggestions": []}
        ]
        stats = {"total_files": 1, "total_lines": 10, "languages": {"Python": {"files": 1, "lines": 10}}}

        with patch("repo_analyze.analyzer._call_claude", return_value="## Overview\n\nThis project does X."):
            result = analyzer.generate_executive_summary(file_analyses, stats, "tree/")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_analyses(self):
        stats = {"total_files": 0, "total_lines": 0, "languages": {}}

        with patch("repo_analyze.analyzer._call_claude", return_value="Empty project."):
            result = analyzer.generate_executive_summary([], stats, "tree/")

        assert isinstance(result, str)

    def test_passes_max_tokens_2048(self):
        stats = {"total_files": 1, "total_lines": 10, "languages": {}}

        with patch("repo_analyze.analyzer._call_claude", return_value="summary") as mock_call:
            analyzer.generate_executive_summary([], stats, "tree/")

        assert mock_call.call_args[1]["max_tokens"] == 2048


class TestGenerateClaudeMd:
    def test_returns_string(self):
        file_analyses = [
            {"path": "main.py", "role": "entrypoint", "summary": "Entry.", "suggestions": []}
        ]
        stats = {"total_files": 1, "total_lines": 5, "languages": {}}

        with patch("repo_analyze.analyzer._call_claude", return_value="# CLAUDE.md\n\nProject info here."):
            result = analyzer.generate_claude_md(file_analyses, stats, "tree/")

        assert isinstance(result, str)

    def test_limits_suggestions_sent_to_claude(self):
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

        with patch("repo_analyze.analyzer._call_claude", return_value="# CLAUDE.md") as mock_call:
            analyzer.generate_claude_md(file_analyses, stats, "tree/")

        prompt_sent = mock_call.call_args[0][0]
        suggestion_lines = [l for l in prompt_sent.splitlines() if l.startswith("- [")]
        assert len(suggestion_lines) <= 20

    def test_passes_max_tokens_4096(self):
        stats = {"total_files": 1, "total_lines": 5, "languages": {}}

        with patch("repo_analyze.analyzer._call_claude", return_value="# CLAUDE.md") as mock_call:
            analyzer.generate_claude_md([], stats, "tree/")

        assert mock_call.call_args[1]["max_tokens"] == 4096
