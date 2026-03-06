# repo-analyze

A CLI tool that uses Claude to onboard developers into unfamiliar codebases.

Given a GitHub URL or local directory, it builds a file tree, analyzes key files with Claude, and writes three Markdown output files:

- `file_summaries.md` — per-file role, summary, and suggestions
- `report.md` — executive summary, repo stats, and file tree
- `CLAUDE.md` — optional AI assistant context file (with `--claude-md`)

## Requirements

You need one of:

- **Claude CLI** — install [Claude Code](https://claude.ai/code) and run `claude` from your terminal _(no API key needed)_
- **Anthropic API key** — set `ANTHROPIC_API_KEY` in your environment or a `.env` file

If both are present, the API key takes priority. If the API key is invalid, the Claude CLI is used as a fallback.

## Install

```bash
pip install -e .
```

To use the API key backend, copy `.env.example` to `.env` and add your key:

```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=your_key_here
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
