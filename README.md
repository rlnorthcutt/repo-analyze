# repo-analyze

A CLI tool that uses the Anthropic Claude API to onboard developers into unfamiliar codebases.

Given a GitHub URL or local directory, it builds a file tree, analyzes key files with Claude, and writes three Markdown output files:

- `file_summaries.md` — per-file role, summary, and suggestions
- `report.md` — executive summary, repo stats, and file tree
- `CLAUDE.md` — optional AI assistant context file (with `--claude-md`)

## Install

```bash
pip install -e .
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
```

## Usage

```bash
# Partial mode (default) — Claude picks the most important files
repo-analyze https://github.com/owner/repo

# Full mode — analyze every file
repo-analyze ./local/project --full

# Generate a CLAUDE.md for the analyzed repo
repo-analyze https://github.com/owner/repo --claude-md

# Custom output directory
repo-analyze https://github.com/owner/repo -o ./output
```

## Development

```bash
pip install -e ".[dev]"
pytest tests/
```
