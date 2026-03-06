import argparse
import sys
import tempfile
import time
from pathlib import Path

from repo_analyze import fetcher, reporter
from repo_analyze import analyzer
from repo_analyze import stats as stats_mod


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="repo-analyze",
        description="Analyze a GitHub repo or local directory with Claude AI.",
    )
    parser.add_argument("source", help="GitHub URL or local directory path")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Analyze all files (default: Claude selects key files)",
    )
    parser.add_argument(
        "--claude-md",
        action="store_true",
        help="Generate a CLAUDE.md for the analyzed repo",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=".",
        help="Output directory for report files (default: current directory)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        # Step 1/5: Acquire repo
        print(f"Acquiring: {args.source}")
        try:
            repo_path, _ = fetcher.get_repo(args.source, tmp_dir)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        # Step 2/5: Build file tree
        print("Building file tree...")
        files = fetcher.build_file_tree(repo_path)
        tree_str = fetcher.build_tree_str(repo_path, files)
        stats = stats_mod.compute_stats(files, repo_path)

        if not files:
            print("No files found to analyze.", file=sys.stderr)
            sys.exit(1)

        print(f"Found {stats['total_files']} files ({stats['total_lines']} lines)")

        # Step 3/5: Select files for analysis
        if args.full:
            selected = files
            print(f"Full mode: analyzing all {len(selected)} files")
        else:
            print("Selecting key files...")
            try:
                selected = analyzer.select_key_files(files, repo_path, tree_str)
                if not selected:
                    selected = files[:20]
                    print("Warning: no files selected by Claude, falling back to first 20")
            except Exception as e:
                print(f"Warning: file selection failed ({e}), using first 20 files")
                selected = files[:20]
            print(f"Selected {len(selected)} files for analysis")

        # Step 4/5: Analyze files
        file_analyses: list[dict] = []
        failed = 0
        for i, f in enumerate(selected, 1):
            rel = f.relative_to(repo_path)
            print(f"  [{i}/{len(selected)}] {rel}")
            try:
                analysis = analyzer.analyze_file(f, repo_path)
                file_analyses.append(analysis)
            except Exception as e:
                print(f"    Warning: failed ({e})")
                file_analyses.append(
                    {
                        "path": str(rel),
                        "role": "other",
                        "summary": "Analysis failed.",
                        "suggestions": [],
                    }
                )
                failed += 1
            time.sleep(0.1)

        if failed:
            print(f"Warning: {failed} file(s) could not be analyzed")

        # Step 5/5: Write reports
        print("Generating reports...")
        try:
            executive_summary = analyzer.generate_executive_summary(
                file_analyses, stats, tree_str
            )
        except Exception as e:
            print(f"Warning: executive summary failed ({e})")
            executive_summary = "_Executive summary generation failed._"

        summaries_path = reporter.write_file_summaries(file_analyses, output_dir)
        report_path = reporter.write_report(executive_summary, stats, tree_str, output_dir)

        if args.claude_md:
            try:
                claude_md_content = analyzer.generate_claude_md(
                    file_analyses, stats, tree_str
                )
            except Exception as e:
                print(f"Warning: CLAUDE.md generation failed ({e})")
                claude_md_content = "# CLAUDE.md\n\n_Generation failed._"
            claude_md_path = reporter.write_claude_md(claude_md_content, output_dir)
            print(f"  {claude_md_path}")

        print(f"\nDone.")
        print(f"  {summaries_path}")
        print(f"  {report_path}")
