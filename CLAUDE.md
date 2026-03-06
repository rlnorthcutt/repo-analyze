# CLAUDE.md — repo-analyze

## Project Overview

`repo-analyze` is a CLI tool that uses the Anthropic Claude API to onboard developers into unfamiliar codebases. Given a GitHub URL or local directory, it builds a file tree, optionally clones the repo, analyzes key files with Claude, and writes three Markdown output files: a per-file summary (`file_summaries.md`), an executive summary report (`report.md`), and an optional `CLAUDE.md` for the analyzed repo.

The tool is installable as a Python package (`pip install -e .`) and exposes a single CLI entrypoint: `repo-analyze`.

---

## Architecture & Key Patterns

**Linear pipeline, no shared state.** The five steps in `cli.py::main()` run sequentially — acquire → tree → select → analyze → report. Each step produces plain Python data structures (lists of `Path`, dicts, strings) that are passed explicitly to the next step. There is no global state, no class instances, no dependency injection framework.

**All Claude calls live in `analyzer.py`.** This is the only file that imports `anthropic`. Every function in it follows the same pattern: build a prompt string with f-strings, call `client.messages.create()`, strip potential markdown fences from the response, parse JSON (for structured outputs) or return raw text (for prose outputs). New Claude-powered features belong here.

**Structured outputs via prompted JSON.** Claude is instructed to respond with a raw JSON object (no fences). The caller does a best-effort fence strip, then `json.loads()`. The schema is defined in the prompt itself — there are no Pydantic models or dataclasses for API responses. If you add a new field to a prompt's schema, update all callers that consume that dict.

**`file_analyses` is the central data artifact.** It's a `list[dict]` where each dict has keys: `path` (str), `role` (str), `summary` (str), `suggestions` (list of dicts with `type` and `description`). This structure flows from `analyzer.analyze_file()` → `cli.py` → `reporter.write_file_summaries()` and `analyzer.generate_executive_summary()`. Don't change this shape without updating all consumers.

**Two analysis modes.** Partial mode calls `select_key_files()` first to get a Claude-curated subset; full mode skips that and passes all files. The mode selection and fallback heuristic both live in `cli.py::main()`.

---

## Directory Structure

```
repo-analyze/
├── repo_analyze/         # The installable package
│   ├── __init__.py       # Version string only
│   ├── cli.py            # Entry point + orchestration (main pipeline lives here)
│   ├── fetcher.py        # Repo acquisition, file tree walk, noise filtering
│   ├── stats.py          # Language detection, line counting, stats dict assembly
│   ├── analyzer.py       # ALL Claude API calls — the only file that touches anthropic
│   └── reporter.py       # Assembles and writes the three output .md files
├── pyproject.toml        # Package metadata, dependencies, CLI entrypoint declaration
├── .env.example          # Template for ANTHROPIC_API_KEY
├── .gitignore
└── README.md
```

There are no subdirectories inside `repo_analyze/`. Keep it flat.

---

## Development Conventions

**Python 3.11+ only.** Use `str | None` union syntax (not `Optional[str]`), `list[Path]` (not `List[Path]`), and `tuple[Path, Path | None]` for return type hints. `match` statements are acceptable.

**`pathlib.Path` everywhere.** Never use `os.path.join()` or string concatenation for file paths. Function signatures should accept and return `Path` objects. Convert to `str` only at the point of writing to a prompt or output file.

**Return plain dicts, not dataclasses.** The `file_analyses` list and `stats` dict are plain `dict` objects. Don't add Pydantic models unless the project gains a public API surface that needs validation.

**Prompts are f-strings in-function.** Don't extract prompts to a separate file or constants module. Keep each prompt co-located with the function that uses it — it makes the input/output contract obvious when reading the code.

**Error handling is try/except in `cli.py`, not in modules.** Individual modules (`analyzer.py`, `fetcher.py`) raise exceptions directly. The orchestration layer in `cli.py` catches them, prints a user-friendly message, and decides whether to abort or continue. Don't add silent error swallowing in module code.

**Rate limiting is a `time.sleep(0.1)` between file analyses.** This is intentionally minimal. Don't add complex retry logic unless the project starts hitting rate limits regularly.

**Output files are always UTF-8.** All `Path.write_text()` and `Path.read_text()` calls must pass `encoding="utf-8"`. Binary/image files are filtered out by `fetcher.should_ignore()` before any read attempt.

---

## Key Files Reference

| File | Role | What to know |
|------|------|--------------|
| `cli.py` | Entry point | The full pipeline lives in `main()`. Steps are labeled with comments (`Step 1/5` etc.). This is the right place to add new pipeline stages or CLI flags. |
| `analyzer.py` | Claude API layer | Four public functions: `select_key_files`, `analyze_file`, `generate_executive_summary`, `generate_claude_md`. All return either a parsed dict or a markdown string. `_client()` is a factory — it re-creates the client on every call. |
| `fetcher.py` | Repo acquisition | `get_repo()` is the main entry. `IGNORE_DIRS`, `IGNORE_EXTENSIONS`, `IGNORE_FILENAMES` are the noise filter lists — add entries here when new junk files appear in analysis. |
| `stats.py` | Language stats | `LANGUAGE_MAP` maps extensions to display names. `compute_stats()` returns the canonical stats dict shape used throughout. `format_stats_section()` renders it as a Markdown table. |
| `reporter.py` | Output writing | Three public functions, one per output file. `write_file_summaries()` groups analyses by role using `ROLE_ICONS` and `SUGGESTION_ICONS` dicts. |
| `pyproject.toml` | Package config | The `[project.scripts]` entry wires `repo-analyze` CLI to `repo_analyze.cli:main`. Dependencies are minimal: `anthropic` and `python-dotenv`. |

---

## Common Tasks

**Install for development:**
```bash
pip install -e .
cp .env.example .env
# Add ANTHROPIC_API_KEY to .env
```

**Run the tool:**
```bash
# Partial mode (default) — Claude picks key files
repo-analyze https://github.com/owner/repo

# Full mode — every file
repo-analyze ./local/project --full

# With CLAUDE.md generation
repo-analyze https://github.com/owner/repo --claude-md

# Custom output dir
repo-analyze https://github.com/owner/repo -o ./output
```

**Add a new language to stats:**
Edit `LANGUAGE_MAP` in `stats.py`. Key is the lowercase extension (e.g. `".zig"`), value is the display name (e.g. `"Zig"`). For files detected by name (e.g. `Makefile`), add to `FILENAME_LANGUAGE_MAP` instead.

**Add a new CLI flag:**
1. Add `parser.add_argument(...)` in `cli.py::main()`
2. Thread the value through the pipeline as a parameter
3. Handle it in the appropriate module

**Add a new Claude-powered step:**
1. Write a new function in `analyzer.py` following the existing pattern (build prompt → call API → strip fences → parse/return)
2. Call it from the appropriate step in `cli.py::main()`
3. Pass results to `reporter.py` if they produce output

---

## Testing

**Framework:** `pytest`. Run with `pytest tests/` from the project root.

**Install dev dependencies:**
```bash
pip install -e ".[dev]"
```

**Test location:** All tests live in `tests/` as a flat directory — no subdirectories. One test file per source module:

| Test file | Module tested |
|-----------|---------------|
| `tests/test_fetcher.py` | `fetcher.py` |
| `tests/test_stats.py` | `stats.py` |
| `tests/test_analyzer.py` | `analyzer.py` |
| `tests/test_reporter.py` | `reporter.py` |

**No real API calls in tests.** All tests that exercise `analyzer.py` must mock `anthropic.Anthropic` using `unittest.mock.patch`:

```python
from unittest.mock import patch, MagicMock

with patch("repo_analyze.analyzer.anthropic.Anthropic") as MockClient:
    MockClient.return_value.messages.create.return_value = mock_response
    result = analyzer.analyze_file(...)
```

**Test naming:** Use `class Test<FunctionName>` grouping with `def test_<behavior>` methods. Each test asserts one specific behavior.

**Use `tmp_path`** (pytest fixture) for any test that reads or writes files. Never hardcode paths.

**Do not suppress exceptions in tests.** If a function is supposed to raise, use `pytest.raises`. If it should succeed, let unexpected exceptions fail the test naturally.

---

## What to Avoid

**Don't instantiate `anthropic.Anthropic` outside `analyzer.py`.** All API access is intentionally centralized there. If you need Claude elsewhere, add a function to `analyzer.py`.

**Don't use `os.path` or string path joins.** Always use `pathlib.Path` and its `/` operator.

**Don't add required arguments to module functions that `cli.py` already has.** Keep module functions independently testable — they shouldn't import `argparse` or read from `sys.argv`.

**Don't suppress exceptions in `analyzer.py`.** The try/except in `cli.py`'s file analysis loop handles failures gracefully (records a stub analysis and increments `failed`). If `analyze_file()` swallowed its own exceptions, failed files would silently produce empty results.

**Don't write output files outside `reporter.py`.** All disk writes for final outputs go through the three `write_*` functions. Intermediate data (the `file_analyses` list, `stats` dict, `tree_str`) stays in memory in `cli.py`.

**Don't change the `file_analyses` dict shape without updating all consumers.** The keys `path`, `role`, `summary`, and `suggestions` are referenced in `reporter.py`, `analyzer.generate_executive_summary()`, and `analyzer.generate_claude_md()`. They are also part of the prompt schema sent to Claude.
