from pathlib import Path

from repo_analyze.stats import format_stats_section

ROLE_ICONS: dict[str, str] = {
    "entrypoint": "[entry]",
    "core": "[core]",
    "config": "[config]",
    "test": "[test]",
    "docs": "[docs]",
    "util": "[util]",
    "data": "[data]",
    "build": "[build]",
    "other": "[other]",
}

SUGGESTION_ICONS: dict[str, str] = {
    "improvement": "[+]",
    "refactor": "[~]",
    "security": "[!]",
    "performance": "[>]",
    "docs": "[d]",
}

ROLE_ORDER = ["entrypoint", "core", "config", "build", "util", "data", "test", "docs", "other"]


def write_file_summaries(file_analyses: list[dict], output_dir: Path) -> Path:
    """Write per-file summaries grouped by role. Returns the output path."""
    lines = ["# File Summaries", ""]

    by_role: dict[str, list[dict]] = {}
    for a in file_analyses:
        role = a.get("role", "other")
        by_role.setdefault(role, []).append(a)

    for role in ROLE_ORDER:
        if role not in by_role:
            continue
        icon = ROLE_ICONS.get(role, "[other]")
        lines.append(f"## {icon} {role.capitalize()}")
        lines.append("")

        for a in by_role[role]:
            lines.append(f"### `{a['path']}`")
            lines.append("")
            lines.append(a.get("summary", "No summary available."))
            lines.append("")

            suggestions = a.get("suggestions", [])
            if suggestions:
                lines.append("**Suggestions:**")
                lines.append("")
                for s in suggestions:
                    icon_s = SUGGESTION_ICONS.get(s.get("type", ""), "[-]")
                    lines.append(f"- {icon_s} **{s.get('type', '')}:** {s.get('description', '')}")
                lines.append("")

            lines.append("---")
            lines.append("")

    output_path = output_dir / "file_summaries.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def write_report(executive_summary: str, stats: dict, tree_str: str, output_dir: Path) -> Path:
    """Write the executive summary report. Returns the output path."""
    stats_section = format_stats_section(stats)

    content = f"""# Repository Analysis Report

{executive_summary}

## Repository Statistics

{stats_section}

## File Tree

```
{tree_str}
```
"""

    output_path = output_dir / "report.md"
    output_path.write_text(content, encoding="utf-8")
    return output_path


def write_claude_md(content: str, output_dir: Path) -> Path:
    """Write the generated CLAUDE.md. Returns the output path."""
    output_path = output_dir / "CLAUDE.md"
    output_path.write_text(content, encoding="utf-8")
    return output_path
