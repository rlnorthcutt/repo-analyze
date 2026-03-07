import random
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.text import Text

from repo_analyze import analyzer, fetcher, reporter
from repo_analyze import stats as stats_mod

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)
console = Console()

VALID_REPORTS = {"onboarding", "improvement", "claude", "all"}

REPORT_DEFS = [
    (
        "onboarding",
        "Onboarding Guide",
        "ONBOARDING.md",
        "Executive summary, language stats, and file tree",
    ),
    (
        "improvement",
        "Code Analysis",
        "ANALYSIS.md",
        "Per-file role summaries and improvement suggestions",
    ),
    (
        "claude",
        "CLAUDE.md",
        "CLAUDE.md",
        "AI assistant context file for use with Claude Code",
    ),
]

ACTION_VERBS = [
    "Analyzing", "Auditing", "Bottlenecking", "Catching", "Collimating", "Combing thru",
    "Compiling", "Computing", "Conceptualizing", "Considering", "Contemplating",
    "Crunching", "Deconstructing", "Decoding", "Decompiling", "Deliberating about",
    "Detecting", "Diagnosing", "Digesting", "Dissecting", "Distilling", "Evaluating",
    "Examining", "Exploring", "Fact-checking", "Filtering", "Gleaning from", "Identifying",
    "Indexing", "Inferring about", "Inspecting", "Interpreting", "Investigating", "Linting",
    "Mapping", "Meditating on", "Navigating", "Optimizing", "Overhauling", "Parsing",
    "Polishing", "Probing", "Processing", "Profiling", "Querying", "Reconstructing",
    "Refining", "Reflecting on", "Reviewing", "Scanning", "Scrutinizing", "Sifting thru",
    "Simulating", "Sorting", "Streamlining", "Studying", "Summarizing", "Synthesizing",
    "Tokenizing", "Tracing", "Traversing", "Troubleshooting", "Unraveling", "Validating",
    "Vetting", "Visualizing", "Weighing", "Winnowing", "Wondering about", "X-raying",
]

ROLE_COLORS = {
    "entrypoint": "bold green",
    "core": "bold blue",
    "config": "yellow",
    "test": "cyan",
    "docs": "white",
    "util": "dim white",
    "data": "magenta",
    "build": "dark_orange",
    "other": "dim",
}


# ── Interactive prompts ────────────────────────────────────────────────────────

def _show_banner() -> None:
    console.print()
    console.print(Panel(
        Text.from_markup(
            "[bold white]repo-analyze[/bold white]\n"
            "[dim]Onboard any codebase with Claude AI[/dim]"
        ),
        border_style="blue",
        padding=(1, 6),
        expand=False,
    ))
    console.print()


def _prompt_source() -> str:
    console.print(Rule("[dim]Repository[/dim]", style="dim blue"))
    console.print()
    value = Prompt.ask(
        "  [bold]GitHub URL or local path[/bold]",
        console=console,
    )
    console.print()
    return value.strip()


def _prompt_reports() -> set[str]:
    selected: set[str] = {r[0] for r in REPORT_DEFS}  # all on by default

    # Panel dimensions (must stay in sync with the Panel rendered below):
    #   top border(1) + top padding(1) + content(N×2) + bottom padding(1) + bottom border(1)
    panel_lines = 4 + len(REPORT_DEFS) * 2

    def _render_panel() -> Panel:
        lines = []
        for i, (key, name, file, desc) in enumerate(REPORT_DEFS, 1):
            if key in selected:
                check = "[bold green]✓[/bold green]"
                name_style = f"[bold]{name}[/bold]"
            else:
                check = "[dim]·[/dim]"
                name_style = f"[dim]{name}[/dim]"
            lines.append(
                f"  [bold]{i}[/bold]  {check}  {name_style}  [dim]{file}[/dim]"
            )
            lines.append(f"          [dim]{desc}[/dim]")
        return Panel(
            "\n".join(lines),
            subtitle="[dim]enter a number to toggle · Enter to confirm[/dim]",
            border_style="blue",
            padding=(1, 2),
        )

    console.print(Rule("[dim]Reports[/dim]", style="dim blue"))
    console.print()

    first = True
    while True:
        if not first:
            # Erase the previous panel + prompt line in-place
            sys.stdout.write(f"\033[{panel_lines + 1}A\033[J")
            sys.stdout.flush()
        first = False

        console.print(_render_panel())

        raw = Prompt.ask(
            "  [bold]Toggle[/bold]",
            default="",
            console=console,
            show_default=False,
        )

        if raw.strip() == "":
            break

        for token in raw.replace(",", " ").split():
            try:
                idx = int(token) - 1
                if 0 <= idx < len(REPORT_DEFS):
                    key = REPORT_DEFS[idx][0]
                    candidate = selected.symmetric_difference({key})
                    if candidate:  # never allow empty selection
                        selected = candidate
            except ValueError:
                for key, name, _, _ in REPORT_DEFS:
                    if token.lower() == key.lower():
                        candidate = selected.symmetric_difference({key})
                        if candidate:
                            selected = candidate

    console.print()
    return selected


def _prompt_full() -> bool:
    console.print(Rule("[dim]Analysis scope[/dim]", style="dim blue"))
    console.print()
    result = Confirm.ask(
        "  [bold]Analyze every file?[/bold] [dim](default: Claude selects key files)[/dim]",
        default=False,
        console=console,
    )
    console.print()
    return result


def _prompt_output() -> Path:
    console.print(Rule("[dim]Output[/dim]", style="dim blue"))
    console.print()
    raw = Prompt.ask(
        "  [bold]Output directory[/bold]",
        default=".",
        console=console,
    )
    console.print()
    return Path(raw.strip())


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_reports(value: str) -> set[str]:
    parts = {r.strip().lower() for r in value.split(",")}
    invalid = parts - VALID_REPORTS
    if invalid:
        raise typer.BadParameter(
            f"Unknown report type(s): {', '.join(sorted(invalid))}. "
            f"Valid options: onboarding, improvement, claude, all"
        )
    if "all" in parts:
        return {"onboarding", "improvement", "claude"}
    return parts


def _show_analysis(analysis: dict) -> None:
    role = analysis.get("role", "other")
    summary = analysis.get("summary", "")
    path = analysis.get("path", "")

    color = ROLE_COLORS.get(role, "dim")
    content = f"[{color}]{role}[/{color}]  {escape(summary)}"

    console.print(
        Panel(
            content,
            title=f"[bold]{escape(path)}[/bold]",
            title_align="left",
            border_style="blue",
            padding=(0, 1),
        )
    )


# ── Entry point ────────────────────────────────────────────────────────────────

@app.command()
def main(
    source: Optional[str] = typer.Argument(None, help="GitHub URL or local directory path"),
    full: Optional[bool] = typer.Option(
        None,
        "--full/--no-full",
        help="Analyze all files (default: Claude selects key files)",
    ),
    reports: Optional[str] = typer.Option(
        None,
        "--reports",
        help="Comma-separated reports to generate: onboarding, improvement, claude, all",
    ),
    output: Optional[Path] = typer.Option(
        None, "-o", "--output", help="Output directory for report files"
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Skip all prompts; use defaults for any unset flags. Required when SOURCE is omitted in CI/scripts.",
    ),
) -> None:
    interactive = sys.stdin.isatty() and sys.stdout.isatty() and not non_interactive
    needs_wizard = interactive and any(v is None for v in [source, reports, full, output])

    if needs_wizard:
        _show_banner()

    # ── source ──
    if source is None:
        if interactive:
            source = _prompt_source()
        else:
            console.print("[red]Error:[/red] Missing required argument SOURCE.")
            raise typer.Exit(1)
    if not source.strip():
        console.print("[red]Error:[/red] Repository source cannot be empty.")
        raise typer.Exit(1)

    # ── reports ──
    if reports is None:
        selected_reports = _prompt_reports() if interactive else {"onboarding", "improvement", "claude"}
    else:
        try:
            selected_reports = _parse_reports(reports)
        except typer.BadParameter as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

    # ── full scan ──
    if full is None:
        full = _prompt_full() if interactive else False

    # ── output dir ──
    if output is None:
        output = _prompt_output() if interactive else Path(".")

    output.mkdir(parents=True, exist_ok=True)

    try:
        _run(source, full, selected_reports, output)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        raise typer.Exit(130)


# ── Pipeline ───────────────────────────────────────────────────────────────────

def _run(source: str, full: bool, reports: set[str], output_dir: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        # Step 1/5: Acquire repo
        with console.status(f"Acquiring [bold]{escape(source)}[/bold]..."):
            try:
                repo_path, _ = fetcher.get_repo(source, tmp_dir)
            except Exception as e:
                console.print(f"[red]Error:[/red] {e}")
                raise typer.Exit(1)

        # Step 2/5: Build file tree
        with console.status("Building file tree..."):
            files = fetcher.build_file_tree(repo_path)
            tree_str = fetcher.build_tree_str(repo_path, files)
            stats = stats_mod.compute_stats(files, repo_path)

        if not files:
            console.print("[red]No files found to analyze.[/red]")
            raise typer.Exit(1)

        console.print(
            f"Found [bold]{stats['total_files']}[/bold] files "
            f"([dim]{stats['total_lines']} lines[/dim])"
        )

        # Step 3/5: Select files for analysis
        if full:
            selected = files
            console.print(f"Full mode: analyzing all [bold]{len(selected)}[/bold] files")
        else:
            with console.status("Selecting key files..."):
                try:
                    selected = analyzer.select_key_files(files, repo_path, tree_str)
                    if not selected:
                        selected = files[:20]
                        console.print(
                            "[yellow]Warning:[/yellow] no files selected by Claude, "
                            "falling back to first 20"
                        )
                except Exception as e:
                    console.print(
                        f"[yellow]Warning:[/yellow] file selection failed ({e}), "
                        "using first 20 files"
                    )
                    selected = files[:20]
            console.print(f"Selected [bold]{len(selected)}[/bold] files for analysis")

        # Step 4/5: Analyze files
        file_analyses: list[dict] = []
        failed = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
            transient=False,
        ) as progress:
            task = progress.add_task("Analyzing...", total=len(selected))
            for f in selected:
                rel = f.relative_to(repo_path)
                verb = random.choice(ACTION_VERBS)
                progress.update(task, description=f"{verb} [dim]{escape(str(rel))}[/dim]")
                try:
                    analysis = analyzer.analyze_file(f, repo_path)
                    file_analyses.append(analysis)
                    _show_analysis(analysis)
                except Exception as e:
                    console.print(f"[yellow]  Warning:[/yellow] {escape(str(rel))} failed ({e})")
                    file_analyses.append(
                        {
                            "path": str(rel),
                            "role": "other",
                            "summary": "Analysis failed.",
                            "suggestions": [],
                        }
                    )
                    failed += 1
                progress.advance(task)
                time.sleep(0.1)

        if failed:
            console.print(f"[yellow]Warning:[/yellow] {failed} file(s) could not be analyzed")

        # Step 5/5: Write reports
        md_files = [str(f.relative_to(repo_path)) for f in files if f.suffix.lower() == ".md"]
        output_paths: list[Path] = []

        if "improvement" in reports:
            output_paths.append(reporter.write_file_summaries(file_analyses, output_dir))

        if "onboarding" in reports:
            with console.status("Generating onboarding guide..."):
                try:
                    executive_summary = analyzer.generate_executive_summary(
                        file_analyses, stats, tree_str
                    )
                except Exception as e:
                    console.print(f"[yellow]Warning:[/yellow] executive summary failed ({e})")
                    executive_summary = "_Executive summary generation failed._"
            output_paths.append(
                reporter.write_report(
                    executive_summary,
                    stats,
                    tree_str,
                    output_dir,
                    repo_name=repo_path.name,
                    md_files=md_files,
                )
            )

        if "claude" in reports:
            with console.status("Generating CLAUDE.md..."):
                try:
                    claude_md_content = analyzer.generate_claude_md(
                        file_analyses, stats, tree_str
                    )
                except Exception as e:
                    console.print(f"[yellow]Warning:[/yellow] CLAUDE.md generation failed ({e})")
                    claude_md_content = "# CLAUDE.md\n\n_Generation failed._"
            output_paths.append(reporter.write_claude_md(claude_md_content, output_dir))

        console.print()
        console.print("[bold green]Done.[/bold green]")
        for p in output_paths:
            console.print(f"  [dim]{p}[/dim]")
