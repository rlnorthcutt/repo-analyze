import json
import os
import shutil
import subprocess
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-opus-4-6"
MAX_FILE_CHARS = 8_000


def _has_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _has_claude_cli() -> bool:
    return shutil.which("claude") is not None


def _call_claude(prompt: str, max_tokens: int = 1024) -> str:
    """Call Claude via the SDK (if API key is set) or the Claude CLI as a fallback.

    If ANTHROPIC_API_KEY is set but invalid, falls through to the CLI.
    Raises RuntimeError if no working backend is found.
    """
    if _has_api_key():
        try:
            client = anthropic.Anthropic()
            response = client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except anthropic.AuthenticationError:
            pass  # key present but invalid — fall through to CLI

    if _has_claude_cli():
        result = subprocess.run(
            ["claude", "-p"],
            input=prompt,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    if _has_api_key():
        raise RuntimeError(
            "ANTHROPIC_API_KEY is set but authentication failed. "
            "Check that your key is valid, or unset it to use the Claude CLI."
        )
    raise RuntimeError(
        "No Claude backend available. "
        "Set ANTHROPIC_API_KEY in your environment or .env file, "
        "or install the Claude CLI (https://claude.ai/code)."
    )


def _strip_fences(text: str) -> str:
    """Remove markdown code fences from a response string."""
    text = text.strip()
    if text.startswith("```"):
        newline = text.index("\n")
        text = text[newline + 1:]
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def select_key_files(files: list[Path], root: Path, tree_str: str) -> list[Path]:
    """Ask Claude to select the most important files for understanding the codebase.

    Returns a subset of files ordered by importance.
    """
    file_list = "\n".join(str(f.relative_to(root)) for f in files)
    prompt = f"""You are analyzing a codebase. Given the file tree and file list below, select the most
important files for understanding the architecture and purpose of the project.

Return a JSON object with a single key "files" containing an array of relative file paths.
Choose at most 20 files. Prioritize: entry points, core logic, configuration, and documentation.
Exclude: generated files, assets, and boilerplate.

File tree:
{tree_str}

All files:
{file_list}

Respond with only a raw JSON object, no markdown fences. Example:
{{"files": ["src/main.py", "README.md", "pyproject.toml"]}}"""

    text = _strip_fences(_call_claude(prompt))
    data = json.loads(text)

    selected_rel = set(data["files"])
    return [f for f in files if str(f.relative_to(root)) in selected_rel]


def analyze_file(file_path: Path, root: Path) -> dict:
    """Analyze a single file with Claude and return a structured analysis dict.

    Returns a dict with keys: path, role, summary, suggestions.
    Raises on API or parse errors — caller is responsible for handling.
    """
    content = file_path.read_text(encoding="utf-8", errors="replace")
    if len(content) > MAX_FILE_CHARS:
        content = content[:MAX_FILE_CHARS] + "\n... [truncated]"

    rel_path = str(file_path.relative_to(root))

    prompt = f"""Analyze the following source file and return a JSON object with this exact schema:
{{
  "path": "<relative file path>",
  "role": "<one of: entrypoint, core, config, test, docs, util, data, build, other>",
  "summary": "<2-3 sentence description of what this file does>",
  "suggestions": [
    {{"type": "<one of: improvement, refactor, security, performance, docs>", "description": "<actionable suggestion>"}}
  ]
}}

File: {rel_path}

```
{content}
```

Respond with only a raw JSON object, no markdown fences."""

    text = _strip_fences(_call_claude(prompt))
    data = json.loads(text)
    data["path"] = rel_path  # ensure path is canonical
    return data


def generate_executive_summary(file_analyses: list[dict], stats: dict, tree_str: str) -> str:
    """Generate a prose executive summary of the codebase. Returns a Markdown string."""
    analyses_text = "\n".join(
        f"- {a['path']} ({a.get('role', 'other')}): {a.get('summary', '')}"
        for a in file_analyses
    )
    lang_summary = ", ".join(
        f"{lang} ({counts['files']} files)"
        for lang, counts in sorted(
            stats.get("languages", {}).items(),
            key=lambda x: x[1]["lines"],
            reverse=True,
        )
    )

    prompt = f"""You are writing an executive summary for a developer who is new to this codebase.
Based on the file analyses below, write a clear and concise Markdown summary covering:

1. **Purpose** — What does this project do?
2. **Architecture** — How is it structured? What are the key components?
3. **Key Patterns** — Notable design decisions, conventions, or patterns.
4. **Getting Started** — Where should a new developer start reading?

Languages: {lang_summary or "unknown"}
Total files analyzed: {stats.get("total_files", 0)}

File tree:
{tree_str}

File analyses:
{analyses_text}

Write in clear prose. Use Markdown headers and bullet points where appropriate.
Do not include a top-level H1 title — the report wrapper will add one."""

    return _call_claude(prompt, max_tokens=2048).strip()


def generate_claude_md(file_analyses: list[dict], stats: dict, tree_str: str) -> str:
    """Generate a CLAUDE.md file for the analyzed repo. Returns a Markdown string."""
    analyses_text = "\n".join(
        f"- {a['path']} ({a.get('role', 'other')}): {a.get('summary', '')}"
        for a in file_analyses
    )
    all_suggestions = [
        s
        for a in file_analyses
        for s in a.get("suggestions", [])
    ]
    suggestions_text = "\n".join(
        f"- [{s.get('type', '')}] {s.get('description', '')}"
        for s in all_suggestions[:20]
    )

    prompt = f"""You are generating a CLAUDE.md file for an AI coding assistant that will work on this codebase.

A good CLAUDE.md covers:
1. Project overview (1-2 sentences)
2. Key architecture decisions and patterns
3. Directory structure with role of each folder/file
4. Development conventions (naming, patterns, tooling)
5. Common tasks (how to run, test, build)
6. What to avoid (gotchas, anti-patterns)

File tree:
{tree_str}

File analyses:
{analyses_text}

Top suggestions from analysis:
{suggestions_text or "None"}

Write a complete, well-structured CLAUDE.md. Start with a level-1 heading: # CLAUDE.md"""

    return _call_claude(prompt, max_tokens=4096).strip()
