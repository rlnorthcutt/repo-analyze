import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from repo_analyze.fetcher import (
    should_ignore,
    build_file_tree,
    build_tree_str,
    get_repo,
    _is_github_url,
)


class TestShouldIgnore:
    def test_ignores_git_dir(self):
        assert should_ignore(Path(".git/config")) is True

    def test_ignores_pycache(self):
        assert should_ignore(Path("src/__pycache__/module.cpython-311.pyc")) is True

    def test_ignores_node_modules(self):
        assert should_ignore(Path("node_modules/lodash/index.js")) is True

    def test_ignores_venv(self):
        assert should_ignore(Path(".venv/lib/python3.11/site.py")) is True

    def test_ignores_pyc_extension(self):
        assert should_ignore(Path("src/main.pyc")) is True

    def test_ignores_jpg(self):
        assert should_ignore(Path("assets/logo.jpg")) is True

    def test_ignores_png(self):
        assert should_ignore(Path("docs/screenshot.PNG")) is True  # case-insensitive

    def test_ignores_ds_store(self):
        assert should_ignore(Path("src/.DS_Store")) is True

    def test_ignores_lock_file(self):
        assert should_ignore(Path("package-lock.json")) is True

    def test_does_not_ignore_python(self):
        assert should_ignore(Path("src/main.py")) is False

    def test_does_not_ignore_readme(self):
        assert should_ignore(Path("README.md")) is False

    def test_does_not_ignore_toml(self):
        assert should_ignore(Path("pyproject.toml")) is False

    def test_does_not_ignore_makefile(self):
        assert should_ignore(Path("Makefile")) is False

    def test_does_not_ignore_nested_src(self):
        assert should_ignore(Path("src/core/engine.py")) is False


class TestBuildFileTree:
    def test_returns_list_of_paths(self, tmp_path):
        (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")
        (tmp_path / "utils.py").write_text("pass", encoding="utf-8")

        files = build_file_tree(tmp_path)

        assert len(files) == 2
        assert all(isinstance(f, Path) for f in files)

    def test_excludes_ignored_dirs(self, tmp_path):
        (tmp_path / "main.py").write_text("x", encoding="utf-8")
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "main.cpython-311.pyc").write_bytes(b"")

        files = build_file_tree(tmp_path)

        assert len(files) == 1
        assert files[0].name == "main.py"

    def test_excludes_binary_extensions(self, tmp_path):
        (tmp_path / "script.py").write_text("x", encoding="utf-8")
        (tmp_path / "image.jpg").write_bytes(b"\xff\xd8")

        files = build_file_tree(tmp_path)

        assert len(files) == 1
        assert files[0].name == "script.py"

    def test_returns_absolute_paths(self, tmp_path):
        (tmp_path / "main.py").write_text("x", encoding="utf-8")

        files = build_file_tree(tmp_path)

        assert files[0].is_absolute()

    def test_empty_directory(self, tmp_path):
        files = build_file_tree(tmp_path)
        assert files == []

    def test_nested_files(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "core.py").write_text("x", encoding="utf-8")
        (tmp_path / "README.md").write_text("x", encoding="utf-8")

        files = build_file_tree(tmp_path)

        assert len(files) == 2


class TestBuildTreeStr:
    def test_includes_root_name(self, tmp_path):
        (tmp_path / "main.py").write_text("x", encoding="utf-8")

        tree = build_tree_str(tmp_path, [tmp_path / "main.py"])

        assert tmp_path.name + "/" in tree

    def test_lists_files(self, tmp_path):
        (tmp_path / "main.py").write_text("x", encoding="utf-8")
        (tmp_path / "utils.py").write_text("x", encoding="utf-8")

        files = [tmp_path / "main.py", tmp_path / "utils.py"]
        tree = build_tree_str(tmp_path, files)

        assert "main.py" in tree
        assert "utils.py" in tree

    def test_nested_structure(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "core.py").write_text("x", encoding="utf-8")

        files = [src / "core.py"]
        tree = build_tree_str(tmp_path, files)

        assert "src/" in tree
        assert "core.py" in tree

    def test_empty_files_list(self, tmp_path):
        tree = build_tree_str(tmp_path, [])
        assert tmp_path.name + "/" in tree

    def test_last_item_uses_corner_connector(self, tmp_path):
        (tmp_path / "only.py").write_text("x", encoding="utf-8")
        tree = build_tree_str(tmp_path, [tmp_path / "only.py"])
        assert "└──" in tree


class TestIsGithubUrl:
    def test_https_url(self):
        assert _is_github_url("https://github.com/owner/repo") is True

    def test_http_url(self):
        assert _is_github_url("http://github.com/owner/repo") is True

    def test_ssh_url(self):
        assert _is_github_url("git@github.com:owner/repo.git") is True

    def test_local_path(self):
        assert _is_github_url("/home/user/project") is False

    def test_relative_path(self):
        assert _is_github_url("./my-project") is False

    def test_other_host(self):
        assert _is_github_url("https://gitlab.com/owner/repo") is False


class TestGetRepo:
    def test_local_path_returns_resolved_path(self, tmp_path):
        repo_path, tmp_dir = get_repo(str(tmp_path), tmp_path / "work")
        assert repo_path == tmp_path.resolve()
        assert tmp_dir is None

    def test_nonexistent_path_raises(self, tmp_path):
        with pytest.raises(ValueError, match="does not exist"):
            get_repo(str(tmp_path / "nonexistent"), tmp_path)

    def test_file_path_raises(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("x", encoding="utf-8")
        with pytest.raises(ValueError, match="Not a directory"):
            get_repo(str(f), tmp_path)

    def test_github_url_clones_repo(self, tmp_path):
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        mock_result = MagicMock()
        with patch("repo_analyze.fetcher.subprocess.run", return_value=mock_result) as mock_run:
            repo_path, returned_work_dir = get_repo(
                "https://github.com/owner/repo", work_dir
            )

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "git" in call_args
        assert "clone" in call_args
        assert repo_path == work_dir / "repo"
        assert returned_work_dir == work_dir

    def test_github_clone_failure_raises(self, tmp_path):
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        with patch(
            "repo_analyze.fetcher.subprocess.run",
            side_effect=subprocess.CalledProcessError(128, "git"),
        ):
            with pytest.raises(subprocess.CalledProcessError):
                get_repo("https://github.com/owner/repo", work_dir)
