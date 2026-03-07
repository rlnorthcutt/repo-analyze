from pathlib import Path

import pytest

from repo_analyze import reporter
from repo_analyze.reporter import _guess_md_purpose, _build_md_library


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
        assert path.name == "ANALYSIS.md"

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
        assert path.name == "ONBOARDING.md"

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


class TestGuessMdPurpose:
    def test_readme(self):
        assert "overview" in _guess_md_purpose("README.md").lower()

    def test_changelog(self):
        assert "changelog" in _guess_md_purpose("CHANGELOG.md").lower()

    def test_contributing(self):
        assert "contribution" in _guess_md_purpose("CONTRIBUTING.md").lower()

    def test_claude(self):
        assert "ai" in _guess_md_purpose("CLAUDE.md").lower()

    def test_case_insensitive_stem(self):
        assert "overview" in _guess_md_purpose("readme.md").lower()

    def test_hyphen_in_name(self):
        assert "getting started" in _guess_md_purpose("getting-started.md").lower()

    def test_nested_path(self):
        result = _guess_md_purpose("docs/API.md")
        assert "api" in result.lower() or "documentation" in result.lower()

    def test_unknown_file_in_docs_dir(self):
        assert "documentation" in _guess_md_purpose("docs/random.md").lower()

    def test_unknown_file_defaults_to_documentation(self):
        assert "documentation" in _guess_md_purpose("unknown-file.md").lower()

    def test_partial_match(self):
        # CHANGELOG contains "CHANGE" but stem is "CHANGELOG" — exact match wins
        assert "changelog" in _guess_md_purpose("CHANGELOG.md").lower()


class TestBuildMdLibrary:
    def test_empty_returns_empty_string(self):
        assert _build_md_library([]) == ""

    def test_includes_file_path(self):
        result = _build_md_library(["README.md"])
        assert "README.md" in result

    def test_includes_purpose_guess(self):
        result = _build_md_library(["README.md"])
        assert "overview" in result.lower()

    def test_includes_section_heading(self):
        result = _build_md_library(["README.md"])
        assert "## Documentation Library" in result

    def test_multiple_files_sorted(self):
        result = _build_md_library(["README.md", "CHANGELOG.md", "CONTRIBUTING.md"])
        changelog_pos = result.index("CHANGELOG")
        contributing_pos = result.index("CONTRIBUTING")
        readme_pos = result.index("README")
        # Sorted alphabetically: CHANGELOG < CONTRIBUTING < README
        assert changelog_pos < contributing_pos < readme_pos


class TestWriteReportExtended:
    def test_includes_repo_name_in_heading(self, tmp_path):
        path = reporter.write_report("Summary.", SAMPLE_STATS, "tree", tmp_path, repo_name="my-project")
        content = path.read_text(encoding="utf-8")
        assert "my-project" in content

    def test_heading_format(self, tmp_path):
        path = reporter.write_report("Summary.", SAMPLE_STATS, "tree", tmp_path, repo_name="myrepo")
        content = path.read_text(encoding="utf-8")
        assert "# myrepo" in content

    def test_md_library_included_before_file_tree(self, tmp_path):
        path = reporter.write_report(
            "Summary.", SAMPLE_STATS, "tree", tmp_path,
            md_files=["README.md", "CHANGELOG.md"],
        )
        content = path.read_text(encoding="utf-8")
        assert "Documentation Library" in content
        lib_pos = content.index("Documentation Library")
        tree_pos = content.index("File Tree")
        assert lib_pos < tree_pos

    def test_no_md_files_omits_library(self, tmp_path):
        path = reporter.write_report("Summary.", SAMPLE_STATS, "tree", tmp_path, md_files=[])
        content = path.read_text(encoding="utf-8")
        assert "Documentation Library" not in content

    def test_default_repo_name(self, tmp_path):
        path = reporter.write_report("Summary.", SAMPLE_STATS, "tree", tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "# Repository" in content


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
