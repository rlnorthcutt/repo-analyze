from pathlib import Path

import pytest

from repo_analyze import reporter


SAMPLE_ANALYSES = [
    {
        "path": "src/main.py",
        "role": "entrypoint",
        "summary": "The main entry point for the application.",
        "suggestions": [
            {"type": "improvement", "description": "Add argument validation."},
            {"type": "docs", "description": "Add a module docstring."},
        ],
    },
    {
        "path": "src/utils.py",
        "role": "util",
        "summary": "Utility functions used across the project.",
        "suggestions": [],
    },
    {
        "path": "tests/test_main.py",
        "role": "test",
        "summary": "Unit tests for main.py.",
        "suggestions": [{"type": "improvement", "description": "Add edge case tests."}],
    },
]

SAMPLE_STATS = {
    "total_files": 3,
    "total_lines": 150,
    "languages": {
        "Python": {"files": 3, "lines": 150},
    },
}


class TestWriteFileSummaries:
    def test_creates_file(self, tmp_path):
        path = reporter.write_file_summaries(SAMPLE_ANALYSES, tmp_path)
        assert path.exists()
        assert path.name == "file_summaries.md"

    def test_returns_path_object(self, tmp_path):
        path = reporter.write_file_summaries(SAMPLE_ANALYSES, tmp_path)
        assert isinstance(path, Path)

    def test_output_in_correct_dir(self, tmp_path):
        path = reporter.write_file_summaries(SAMPLE_ANALYSES, tmp_path)
        assert path.parent == tmp_path

    def test_contains_file_paths(self, tmp_path):
        path = reporter.write_file_summaries(SAMPLE_ANALYSES, tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "src/main.py" in content
        assert "src/utils.py" in content
        assert "tests/test_main.py" in content

    def test_contains_summaries(self, tmp_path):
        path = reporter.write_file_summaries(SAMPLE_ANALYSES, tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "The main entry point" in content
        assert "Utility functions" in content

    def test_contains_suggestions(self, tmp_path):
        path = reporter.write_file_summaries(SAMPLE_ANALYSES, tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "Add argument validation" in content
        assert "Add a module docstring" in content

    def test_groups_by_role(self, tmp_path):
        path = reporter.write_file_summaries(SAMPLE_ANALYSES, tmp_path)
        content = path.read_text(encoding="utf-8")
        # Role headers should be present
        assert "Entrypoint" in content
        assert "Util" in content
        assert "Test" in content

    def test_entrypoint_before_test(self, tmp_path):
        path = reporter.write_file_summaries(SAMPLE_ANALYSES, tmp_path)
        content = path.read_text(encoding="utf-8")
        entrypoint_pos = content.index("Entrypoint")
        test_pos = content.index("Test")
        assert entrypoint_pos < test_pos

    def test_utf8_encoding(self, tmp_path):
        analyses = [
            {
                "path": "readme.md",
                "role": "docs",
                "summary": "Documentation with unicode: \u2014 \u00e9 \u4e2d\u6587",
                "suggestions": [],
            }
        ]
        path = reporter.write_file_summaries(analyses, tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "\u4e2d\u6587" in content

    def test_empty_analyses(self, tmp_path):
        path = reporter.write_file_summaries([], tmp_path)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "# File Summaries" in content

    def test_analysis_with_no_suggestions(self, tmp_path):
        analyses = [
            {"path": "util.py", "role": "util", "summary": "Helpers.", "suggestions": []}
        ]
        path = reporter.write_file_summaries(analyses, tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "util.py" in content
        # No suggestions section should appear
        assert "Suggestions" not in content


class TestWriteReport:
    def test_creates_file(self, tmp_path):
        path = reporter.write_report("Summary text.", SAMPLE_STATS, "root/\n└── main.py", tmp_path)
        assert path.exists()
        assert path.name == "report.md"

    def test_returns_path_object(self, tmp_path):
        path = reporter.write_report("Summary.", SAMPLE_STATS, "tree", tmp_path)
        assert isinstance(path, Path)

    def test_contains_executive_summary(self, tmp_path):
        path = reporter.write_report("This is the exec summary.", SAMPLE_STATS, "tree", tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "This is the exec summary." in content

    def test_contains_stats(self, tmp_path):
        path = reporter.write_report("Summary.", SAMPLE_STATS, "tree", tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "Python" in content
        assert "150" in content  # total lines

    def test_contains_file_tree(self, tmp_path):
        tree = "root/\n├── src/\n│   └── main.py\n└── README.md"
        path = reporter.write_report("Summary.", SAMPLE_STATS, tree, tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "main.py" in content
        assert "README.md" in content

    def test_has_top_level_heading(self, tmp_path):
        path = reporter.write_report("Summary.", SAMPLE_STATS, "tree", tmp_path)
        content = path.read_text(encoding="utf-8")
        assert content.startswith("# ")

    def test_utf8_encoding(self, tmp_path):
        path = reporter.write_report("Unicode: \u2014", SAMPLE_STATS, "tree", tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "\u2014" in content

    def test_empty_stats(self, tmp_path):
        stats = {"total_files": 0, "total_lines": 0, "languages": {}}
        path = reporter.write_report("Summary.", stats, "tree", tmp_path)
        assert path.exists()


class TestWriteClaudeMd:
    def test_creates_file(self, tmp_path):
        path = reporter.write_claude_md("# CLAUDE.md\n\nContent.", tmp_path)
        assert path.exists()
        assert path.name == "CLAUDE.md"

    def test_returns_path_object(self, tmp_path):
        path = reporter.write_claude_md("content", tmp_path)
        assert isinstance(path, Path)

    def test_writes_content_verbatim(self, tmp_path):
        content = "# CLAUDE.md\n\nThis is the content."
        path = reporter.write_claude_md(content, tmp_path)
        assert path.read_text(encoding="utf-8") == content

    def test_utf8_encoding(self, tmp_path):
        content = "# CLAUDE.md\n\nUnicode: \u00e9\u4e2d\u6587"
        path = reporter.write_claude_md(content, tmp_path)
        assert path.read_text(encoding="utf-8") == content

    def test_overwrites_existing_file(self, tmp_path):
        existing = tmp_path / "CLAUDE.md"
        existing.write_text("old content", encoding="utf-8")
        reporter.write_claude_md("new content", tmp_path)
        assert existing.read_text(encoding="utf-8") == "new content"
