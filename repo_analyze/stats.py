from pathlib import Path

LANGUAGE_MAP: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".rs": "Rust",
    ".go": "Go",
    ".java": "Java",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".fish": "Shell",
    ".md": "Markdown",
    ".toml": "TOML",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "CSS",
    ".sass": "CSS",
    ".xml": "XML",
    ".sql": "SQL",
    ".r": "R",
    ".jl": "Julia",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".hs": "Haskell",
    ".lua": "Lua",
    ".dart": "Dart",
    ".zig": "Zig",
    ".tf": "Terraform",
    ".vue": "Vue",
    ".svelte": "Svelte",
}

FILENAME_LANGUAGE_MAP: dict[str, str] = {
    "Makefile": "Make",
    "makefile": "Make",
    "Dockerfile": "Docker",
    "dockerfile": "Docker",
    "Justfile": "Just",
    "justfile": "Just",
}


def _detect_language(path: Path) -> str | None:
    if path.name in FILENAME_LANGUAGE_MAP:
        return FILENAME_LANGUAGE_MAP[path.name]
    return LANGUAGE_MAP.get(path.suffix.lower())


def compute_stats(files: list[Path], root: Path) -> dict:
    """Return a stats dict with total_files, total_lines, and per-language counts."""
    total_lines = 0
    languages: dict[str, dict] = {}

    for f in files:
        lang = _detect_language(f)
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            line_count = content.count("\n") + 1 if content else 0
        except Exception:
            line_count = 0

        total_lines += line_count

        if lang:
            if lang not in languages:
                languages[lang] = {"files": 0, "lines": 0}
            languages[lang]["files"] += 1
            languages[lang]["lines"] += line_count

    return {
        "total_files": len(files),
        "total_lines": total_lines,
        "languages": languages,
    }


def format_stats_section(stats: dict) -> str:
    """Render the stats dict as a Markdown table."""
    languages = stats.get("languages", {})
    if not languages:
        return f"- **Files:** {stats['total_files']}\n- **Lines:** {stats['total_lines']}\n"

    sorted_langs = sorted(languages.items(), key=lambda x: x[1]["lines"], reverse=True)

    total_lines = stats.get("total_lines", 0)

    lines = [
        f"- **Total files:** {stats['total_files']}",
        f"- **Total lines:** {stats['total_lines']}",
        "",
        "| Language | Files | Lines | % |",
        "|----------|------:|------:|--:|",
    ]
    for lang, counts in sorted_langs:
        pct = f"{counts['lines'] / total_lines * 100:.1f}%" if total_lines else "0.0%"
        lines.append(f"| {lang} | {counts['files']} | {counts['lines']} | {pct} |")

    return "\n".join(lines)
