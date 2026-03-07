from pathlib import Path

import pytest

from repo_analyze.stats import (
    compute_stats,
    format_stats_section,
    _detect_language,
    LANGUAGE_MAP,
    FILENAME_LANGUAGE_MAP,
)


class TestDetectLanguage:
    def test_python_extension(self, tmp_path):
        assert _detect_language(tmp_path / "main.py") == "Python"

    def test_typescript_extension(self, tmp_path):
        assert _detect_language(tmp_path / "app.ts") == "TypeScript"

    def test_tsx_maps_to_typescript(self, tmp_path):
        assert _detect_language(tmp_path / "App.tsx") == "TypeScript"

    def test_jsx_maps_to_javascript(self, tmp_path):
        assert _detect_language(tmp_path / "App.jsx") == "JavaScript"

    def test_makefile_by_name(self, tmp_path):
        assert _detect_language(tmp_path / "Makefile") == "Make"

    def test_dockerfile_by_name(self, tmp_path):
        assert _detect_language(tmp_path / "Dockerfile") == "Docker"

    def test_unknown_extension_returns_none(self, tmp_path):
        assert _detect_language(tmp_path / "binary.xyz") is None

    def test_case_insensitive_extension(self, tmp_path):
        assert _detect_language(tmp_path / "script.PY") == "Python"

    def test_yaml_yml(self, tmp_path):
        assert _detect_language(tmp_path / "config.yml") == "YAML"
        assert _detect_language(tmp_path / "config.yaml") == "YAML"


class TestComputeStats:
    def test_empty_file_list(self, tmp_path):
        stats = compute_stats([], tmp_path)
        assert stats["total_files"] == 0
        assert stats["total_lines"] == 0
        assert stats["languages"] == {}

    def test_counts_files_and_lines(self, tmp_path):
        f1 = tmp_path / "a.py"
        f1.write_text("line1\nline2\nline3", encoding="utf-8")
        f2 = tmp_path / "b.py"
        f2.write_text("line1\nline2", encoding="utf-8")

        stats = compute_stats([f1, f2], tmp_path)

        assert stats["total_files"] == 2
        assert stats["total_lines"] == 5  # 3 + 2

    def test_groups_by_language(self, tmp_path):
        py_file = tmp_path / "main.py"
        py_file.write_text("x\ny", encoding="utf-8")
        js_file = tmp_path / "app.js"
        js_file.write_text("a\nb\nc", encoding="utf-8")

        stats = compute_stats([py_file, js_file], tmp_path)

        assert "Python" in stats["languages"]
        assert "JavaScript" in stats["languages"]
        assert stats["languages"]["Python"]["files"] == 1
        assert stats["languages"]["JavaScript"]["files"] == 1
        assert stats["languages"]["JavaScript"]["lines"] == 3

    def test_multiple_files_same_language(self, tmp_path):
        f1 = tmp_path / "a.py"
        f1.write_text("x", encoding="utf-8")
        f2 = tmp_path / "b.py"
        f2.write_text("y", encoding="utf-8")

        stats = compute_stats([f1, f2], tmp_path)

        assert stats["languages"]["Python"]["files"] == 2

    def test_unknown_extension_not_in_languages(self, tmp_path):
        f = tmp_path / "data.xyz"
        f.write_text("content", encoding="utf-8")

        stats = compute_stats([f], tmp_path)

        assert stats["total_files"] == 1
        assert stats["languages"] == {}

    def test_single_line_file_counted_correctly(self, tmp_path):
        f = tmp_path / "one.py"
        f.write_text("print('hi')", encoding="utf-8")

        stats = compute_stats([f], tmp_path)

        assert stats["total_lines"] == 1

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("", encoding="utf-8")

        stats = compute_stats([f], tmp_path)

        assert stats["total_lines"] == 0


class TestFormatStatsSection:
    def test_returns_string(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("x", encoding="utf-8")
        stats = compute_stats([f], tmp_path)
        result = format_stats_section(stats)
        assert isinstance(result, str)

    def test_includes_total_files(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("x", encoding="utf-8")
        stats = compute_stats([f], tmp_path)
        result = format_stats_section(stats)
        assert "1" in result

    def test_includes_language_table(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("x\ny", encoding="utf-8")
        stats = compute_stats([f], tmp_path)
        result = format_stats_section(stats)
        assert "Python" in result
        assert "|" in result  # markdown table

    def test_empty_stats_no_crash(self):
        stats = {"total_files": 0, "total_lines": 0, "languages": {}}
        result = format_stats_section(stats)
        assert "0" in result

    def test_sorts_by_lines_descending(self, tmp_path):
        py = tmp_path / "big.py"
        py.write_text("a\nb\nc\nd\ne", encoding="utf-8")
        js = tmp_path / "small.js"
        js.write_text("x", encoding="utf-8")
        stats = compute_stats([py, js], tmp_path)
        result = format_stats_section(stats)
        python_pos = result.index("Python")
        js_pos = result.index("JavaScript")
        assert python_pos < js_pos  # Python (more lines) comes first

    def test_includes_percentage_column(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("a\nb\nc\nd", encoding="utf-8")
        stats = compute_stats([f], tmp_path)
        result = format_stats_section(stats)
        assert "100.0%" in result

    def test_percentage_sums_correctly(self, tmp_path):
        py = tmp_path / "a.py"
        py.write_text("a\nb\nc", encoding="utf-8")  # 3 lines
        js = tmp_path / "b.js"
        js.write_text("x\ny", encoding="utf-8")  # 2 lines — total 5
        stats = compute_stats([py, js], tmp_path)
        result = format_stats_section(stats)
        assert "60.0%" in result  # Python: 3/5
        assert "40.0%" in result  # JS: 2/5
