from pathlib import Path

from repo_analyze.stats import format_stats_section

_MD_PURPOSE: dict[str, str] = {
    "README": "Project overview and getting started guide",
    "CHANGELOG": "Changelog / release history",
    "CHANGES": "Changelog / release history",
    "HISTORY": "Release history",
    "CONTRIBUTING": "Contribution guidelines",
    "CONTRIBUTORS": "List of project contributors",
    "LICENSE": "License information",
    "CLAUDE": "AI coding assistant instructions",
    "ARCHITECTURE": "Architecture and design overview",
    "DESIGN": "Design documentation",
    "API": "API reference",
    "SECURITY": "Security policy",
    "CODE_OF_CONDUCT": "Code of conduct",
    "SUPPORT": "Support guide",
    "INSTALL": "Installation guide",
    "INSTALLATION": "Installation guide",
    "DEPLOYMENT": "Deployment guide",
    "DEPLOY": "Deployment guide",
    "TESTING": "Testing guide",
    "ROADMAP": "Project roadmap",
    "FAQ": "Frequently asked questions",
    "GLOSSARY": "Glossary of terms",
    "TROUBLESHOOTING": "Troubleshooting guide",
    "MIGRATION": "Migration guide",
    "UPGRADE": "Upgrade guide",
    "RELEASE": "Release notes",
    "SETUP": "Setup guide",
    "QUICKSTART": "Quick start guide",
    "GETTING_STARTED": "Getting started guide",
    "GUIDE": "User guide",
    "REFERENCE": "Reference documentation",
    "DEVELOPMENT": "Development guide",
    "DEV": "Development guide",
    "WORKFLOW": "Workflow documentation",
}


def _guess_md_purpose(rel_path: str) -> str:
    """Heuristic guess at what a Markdown file covers based on its name."""
    stem = Path(rel_path).stem.upper().replace("-", "_").replace(" ", "_")
    if stem in _MD_PURPOSE:
        return _MD_PURPOSE[stem]
    for key, desc in _MD_PURPOSE.items():
        if key in stem:
            return desc
    parts = Path(rel_path).parts
    if len(parts) > 1 and parts[0].lower() in ("docs", "documentation", "doc"):
        return "Documentation"
    return "Documentation"


def _build_md_library(md_files: list[str]) -> str:
    """Build a Documentation Library section listing all Markdown files."""
    if not md_files:
        return ""
    lines = ["## Documentation Library", ""]
    for path in sorted(md_files):
        purpose = _guess_md_purpose(path)
        lines.append(f"- `{path}` — {purpose}")
    lines.append("")
    return "\n".join(lines)

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

    output_path = output_dir / "ANALYSIS.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def write_report(
    executive_summary: str,
    stats: dict,
    tree_str: str,
    output_dir: Path,
    *,
    repo_name: str = "Repository",
    md_files: list[str] | None = None,
) -> Path:
    """Write the onboarding guide report. Returns the output path."""
    stats_section = format_stats_section(stats)
    md_library = _build_md_library(md_files or [])

    content = f"""# {repo_name} — Onboarding Guide

{executive_summary}

## Repository Statistics

{stats_section}

{md_library}## File Tree

```
{tree_str}
```
"""

    output_path = output_dir / "ONBOARDING.md"
    output_path.write_text(content, encoding="utf-8")
    return output_path


def write_claude_md(content: str, output_dir: Path) -> Path:
    """Write the generated CLAUDE.md. Returns the output path."""
    output_path = output_dir / "CLAUDE.md"
    output_path.write_text(content, encoding="utf-8")
    return output_path
