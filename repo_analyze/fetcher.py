import subprocess
from pathlib import Path

IGNORE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    ".eggs",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
    "coverage",
    ".tox",
    ".nox",
    ".idea",
    ".vscode",
}

IGNORE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dll",
    ".dylib",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".ico",
    ".webp",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".svg",
    ".db",
    ".sqlite",
    ".bin",
    ".dat",
}

IGNORE_FILENAMES = {
    ".DS_Store",
    "Thumbs.db",
    ".env",
    ".env.local",
    ".env.production",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "uv.lock",
    "poetry.lock",
    "Cargo.lock",
    "composer.lock",
    "Gemfile.lock",
}


def should_ignore(path: Path) -> bool:
    """Return True if this path should be excluded from analysis.

    Checks directory components, filename, and extension.
    path may be relative or absolute.
    """
    for part in path.parts:
        if part in IGNORE_DIRS:
            return True
    if path.name in IGNORE_FILENAMES:
        return True
    if path.suffix.lower() in IGNORE_EXTENSIONS:
        return True
    return False


def is_binary(path: Path) -> bool:
    """Return True if the file appears to be binary (contains null bytes)."""
    try:
        with open(path, "rb") as f:
            return b"\x00" in f.read(8192)
    except OSError:
        return True


def build_file_tree(root: Path) -> list[Path]:
    """Walk root and return all non-ignored, non-binary files, sorted by path."""
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root)
            if not should_ignore(rel) and not is_binary(path):
                files.append(path)
    return files


def build_tree_str(root: Path, files: list[Path]) -> str:
    """Build a visual file tree string from a list of absolute file paths."""
    tree: dict = {}
    for f in files:
        rel = f.relative_to(root)
        node = tree
        for part in rel.parts[:-1]:
            node = node.setdefault(part, {})
        node[rel.parts[-1]] = None  # leaf node

    lines = [root.name + "/"]
    _render_tree(tree, lines, "")
    return "\n".join(lines)


def _render_tree(tree: dict, lines: list[str], prefix: str) -> None:
    entries = sorted(tree.keys())
    for i, name in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = "└── " if is_last else "├── "
        child = tree[name]
        if child is None:
            lines.append(prefix + connector + name)
        else:
            lines.append(prefix + connector + name + "/")
            extension = "    " if is_last else "│   "
            _render_tree(child, lines, prefix + extension)


def _is_github_url(source: str) -> bool:
    return (
        source.startswith("https://github.com/")
        or source.startswith("http://github.com/")
        or source.startswith("git@github.com:")
    )


def get_repo(source: str, work_dir: Path) -> tuple[Path, Path | None]:
    """Acquire a repo from a GitHub URL or local path.

    Returns (repo_path, tmp_dir) where tmp_dir is set if a clone occurred
    and None if the source was a local directory.
    """
    if _is_github_url(source):
        clone_dir = work_dir / "repo"
        subprocess.run(
            ["git", "clone", "--depth=1", source, str(clone_dir)],
            check=True,
            capture_output=True,
            text=True,
        )
        return clone_dir, work_dir

    path = Path(source).resolve()
    if not path.exists():
        raise ValueError(f"Path does not exist: {source}")
    if not path.is_dir():
        raise ValueError(f"Not a directory: {source}")
    return path, None
