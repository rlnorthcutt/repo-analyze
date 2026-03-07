# repo-analyze

A CLI tool that uses Claude to onboard developers into unfamiliar codebases.

Given a GitHub URL or local directory, it builds a file tree, analyzes key files with Claude, and writes up to three Markdown output files:

- `ONBOARDING.md` — executive summary, repo stats, documentation library, and file tree
- `ANALYSIS.md` — per-file role, summary, and improvement suggestions
- `CLAUDE.md` — AI assistant context file for use with Claude Code

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
# Default: analyze key files, generate all three reports, output to current dir
repo-analyze https://github.com/owner/repo

# All flags explicit
repo-analyze https://github.com/owner/repo \
  --full \
  --reports onboarding,improvement,claude \
  --output ./output

# Local path, full scan, only the onboarding guide
repo-analyze ./my-local-project \
  --full \
  --reports onboarding \
  --output ./docs

# Quick CLAUDE.md only (partial file selection, default output dir)
repo-analyze https://github.com/owner/repo --reports claude

# Improvement report + CLAUDE.md, custom output
repo-analyze ./my-local-project --reports improvement,claude -o ./analysis
```

## Flags

| Flag | Values | Default | Description |
|------|--------|---------|-------------|
| `source` | URL or path | *(prompted)* | GitHub URL or local directory |
| `--full` | boolean | off | Analyze every file instead of Claude-selected subset |
| `--reports` | `onboarding`, `improvement`, `claude`, `all` | `all` | Which output files to generate (comma-separated) |
| `-o` / `--output` | path | `.` | Directory to write output files into |
| `--non-interactive` | boolean | off | Skip all prompts; use defaults for unset flags (for CI/scripts) |

## Development

```bash
pip install -e ".[dev]"
pytest tests/
```
