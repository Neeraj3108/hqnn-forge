"""Tests for .github/scripts/check_dist_contents.py."""

from __future__ import annotations

import importlib.util
import io
import tarfile
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _import_script() -> ModuleType:
    path = ROOT / ".github" / "scripts" / "check_dist_contents.py"
    spec = importlib.util.spec_from_file_location("check_dist_contents", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = _import_script()


def _make_wheel(path: Path, files: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)


def _make_sdist(path: Path, files: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w:gz") as t:
        for name, data in files.items():
            encoded = data.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(encoded)
            t.addfile(info, io.BytesIO(encoded))


def test_identical_distributions_pass(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"

    wheel_files = {
        "hqnn_forge/__init__.py": "__version__ = '0.1.0'\n",
        "hqnn_forge-0.1.0.dist-info/METADATA": "Metadata-Version: 2.1\nName: hqnn-forge\nVersion: 0.1.0\n",
    }
    sdist_files = {
        "hqnn_forge-0.1.0/pyproject.toml": "[project]\nname = 'hqnn-forge'\n",
        "hqnn_forge-0.1.0/PKG-INFO": "Metadata-Version: 2.1\nName: hqnn-forge\nVersion: 0.1.0\n",
    }

    _make_wheel(dir_a / "hqnn_forge-0.1.0-py3-none-any.whl", wheel_files)
    _make_wheel(dir_b / "hqnn_forge-0.1.0-py3-none-any.whl", wheel_files)
    _make_sdist(dir_a / "hqnn_forge-0.1.0.tar.gz", sdist_files)
    _make_sdist(dir_b / "hqnn_forge-0.1.0.tar.gz", sdist_files)

    errors = checker.compare(dir_a, dir_b)
    assert errors == []


def test_generator_difference_ignored(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"

    wheel_files_a = {
        "hqnn_forge/__init__.py": "__version__ = '0.1.0'\n",
        "hqnn_forge-0.1.0.dist-info/METADATA": (
            "Metadata-Version: 2.1\nName: hqnn-forge\nGenerator: uv_build 0.13.1\nVersion: 0.1.0\n"
        ),
    }
    wheel_files_b = {
        "hqnn_forge/__init__.py": "__version__ = '0.1.0'\n",
        "hqnn_forge-0.1.0.dist-info/METADATA": (
            "Metadata-Version: 2.1\nName: hqnn-forge\nGenerator: uv_build 0.12.0\nVersion: 0.1.0\n"
        ),
    }

    sdist_files_a = {
        "hqnn_forge-0.1.0/pyproject.toml": "[project]\nname = 'hqnn-forge'\n",
        "hqnn_forge-0.1.0/PKG-INFO": (
            "Metadata-Version: 2.1\nName: hqnn-forge\nGenerator: uv_build 0.13.1\nVersion: 0.1.0\n"
        ),
    }
    sdist_files_b = {
        "hqnn_forge-0.1.0/pyproject.toml": "[project]\nname = 'hqnn-forge'\n",
        "hqnn_forge-0.1.0/PKG-INFO": (
            "Metadata-Version: 2.1\nName: hqnn-forge\nGenerator: uv_build 0.12.0\nVersion: 0.1.0\n"
        ),
    }

    _make_wheel(dir_a / "hqnn_forge-0.1.0-py3-none-any.whl", wheel_files_a)
    _make_wheel(dir_b / "hqnn_forge-0.1.0-py3-none-any.whl", wheel_files_b)
    _make_sdist(dir_a / "hqnn_forge-0.1.0.tar.gz", sdist_files_a)
    _make_sdist(dir_b / "hqnn_forge-0.1.0.tar.gz", sdist_files_b)

    errors = checker.compare(dir_a, dir_b)
    assert errors == []


def test_metadata_difference_reported(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"

    wheel_files_a = {
        "hqnn_forge-0.1.0.dist-info/METADATA": "Metadata-Version: 2.1\nSummary: Original\n",
    }
    wheel_files_b = {
        "hqnn_forge-0.1.0.dist-info/METADATA": "Metadata-Version: 2.1\nSummary: Modified\n",
    }
    sdist_files = {
        "hqnn_forge-0.1.0/PKG-INFO": "Metadata-Version: 2.1\n",
    }

    _make_wheel(dir_a / "hqnn_forge-0.1.0-py3-none-any.whl", wheel_files_a)
    _make_wheel(dir_b / "hqnn_forge-0.1.0-py3-none-any.whl", wheel_files_b)
    _make_sdist(dir_a / "hqnn_forge-0.1.0.tar.gz", sdist_files)
    _make_sdist(dir_b / "hqnn_forge-0.1.0.tar.gz", sdist_files)

    errors = checker.compare(dir_a, dir_b)
    assert len(errors) == 1
    assert any("Wheel METADATA differs" in e for e in errors)
    assert any("-Summary: Original" in e and "+Summary: Modified" in e for e in errors)


def test_sdist_metadata_difference_reported(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"

    wheel_files = {
        "hqnn_forge-0.1.0.dist-info/METADATA": "Metadata-Version: 2.1\n",
    }
    sdist_files_a = {
        "hqnn_forge-0.1.0/PKG-INFO": "Metadata-Version: 2.1\nSummary: Alpha\n",
    }
    sdist_files_b = {
        "hqnn_forge-0.1.0/PKG-INFO": "Metadata-Version: 2.1\nSummary: Beta\n",
    }

    _make_wheel(dir_a / "hqnn_forge-0.1.0-py3-none-any.whl", wheel_files)
    _make_wheel(dir_b / "hqnn_forge-0.1.0-py3-none-any.whl", wheel_files)
    _make_sdist(dir_a / "hqnn_forge-0.1.0.tar.gz", sdist_files_a)
    _make_sdist(dir_b / "hqnn_forge-0.1.0.tar.gz", sdist_files_b)

    errors = checker.compare(dir_a, dir_b)
    assert len(errors) == 1
    assert any("Sdist PKG-INFO differs" in e for e in errors)


def test_wheel_file_manifest_difference(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"

    wheel_files_a = {
        "hqnn_forge/__init__.py": "",
        "hqnn_forge/extra.py": "",
        "hqnn_forge-0.1.0.dist-info/METADATA": "Metadata-Version: 2.1\n",
    }
    wheel_files_b = {
        "hqnn_forge/__init__.py": "",
        "hqnn_forge-0.1.0.dist-info/METADATA": "Metadata-Version: 2.1\n",
    }
    sdist_files = {
        "hqnn_forge-0.1.0/PKG-INFO": "Metadata-Version: 2.1\n",
    }

    _make_wheel(dir_a / "hqnn_forge-0.1.0-py3-none-any.whl", wheel_files_a)
    _make_wheel(dir_b / "hqnn_forge-0.1.0-py3-none-any.whl", wheel_files_b)
    _make_sdist(dir_a / "hqnn_forge-0.1.0.tar.gz", sdist_files)
    _make_sdist(dir_b / "hqnn_forge-0.1.0.tar.gz", sdist_files)

    errors = checker.compare(dir_a, dir_b)
    assert len(errors) == 1
    assert any("Wheel file lists differ" in e for e in errors)
    assert any("hqnn_forge/extra.py" in e for e in errors)


def test_sdist_file_manifest_difference(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"

    wheel_files = {
        "hqnn_forge-0.1.0.dist-info/METADATA": "Metadata-Version: 2.1\n",
    }
    sdist_files_a = {
        "hqnn_forge-0.1.0/PKG-INFO": "Metadata-Version: 2.1\n",
        "hqnn_forge-0.1.0/README.md": "readme\n",
    }
    sdist_files_b = {
        "hqnn_forge-0.1.0/PKG-INFO": "Metadata-Version: 2.1\n",
    }

    _make_wheel(dir_a / "hqnn_forge-0.1.0-py3-none-any.whl", wheel_files)
    _make_wheel(dir_b / "hqnn_forge-0.1.0-py3-none-any.whl", wheel_files)
    _make_sdist(dir_a / "hqnn_forge-0.1.0.tar.gz", sdist_files_a)
    _make_sdist(dir_b / "hqnn_forge-0.1.0.tar.gz", sdist_files_b)

    errors = checker.compare(dir_a, dir_b)
    assert len(errors) == 1
    assert any("Sdist file lists differ" in e for e in errors)


def test_missing_and_ambiguous_archives(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()

    # Missing both wheel and sdist
    errors = checker.compare(dir_a, dir_b)
    assert any("Missing wheel archive in" in e for e in errors)
    assert any("Missing sdist archive in" in e for e in errors)

    # Multiple wheels in a
    _make_wheel(dir_a / "one-0.1.0-py3-none-any.whl", {"one/__init__.py": ""})
    _make_wheel(dir_a / "two-0.1.0-py3-none-any.whl", {"two/__init__.py": ""})
    _make_wheel(dir_b / "one-0.1.0-py3-none-any.whl", {"one/__init__.py": ""})

    errors = checker.compare(dir_a, dir_b)
    assert any("Ambiguous: found multiple wheels" in e for e in errors)


def test_missing_metadata_in_archive(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"

    wheel_files_a = {"hqnn_forge/__init__.py": ""}
    wheel_files_b = {"hqnn_forge/__init__.py": ""}
    sdist_files = {"hqnn_forge-0.1.0/README.md": ""}

    _make_wheel(dir_a / "hqnn_forge-0.1.0-py3-none-any.whl", wheel_files_a)
    _make_wheel(dir_b / "hqnn_forge-0.1.0-py3-none-any.whl", wheel_files_b)
    _make_sdist(dir_a / "hqnn_forge-0.1.0.tar.gz", sdist_files)
    _make_sdist(dir_b / "hqnn_forge-0.1.0.tar.gz", sdist_files)

    errors = checker.compare(dir_a, dir_b)
    assert any("Missing .dist-info/METADATA" in e for e in errors)
    assert any("Missing PKG-INFO" in e for e in errors)


def test_main_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert checker.main([]) == 2

    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()

    wheel_files = {
        "hqnn_forge-0.1.0.dist-info/METADATA": "Metadata-Version: 2.1\n",
    }
    sdist_files = {
        "hqnn_forge-0.1.0/PKG-INFO": "Metadata-Version: 2.1\n",
    }
    _make_wheel(dir_a / "hqnn_forge-0.1.0-py3-none-any.whl", wheel_files)
    _make_wheel(dir_b / "hqnn_forge-0.1.0-py3-none-any.whl", wheel_files)
    _make_sdist(dir_a / "hqnn_forge-0.1.0.tar.gz", sdist_files)
    _make_sdist(dir_b / "hqnn_forge-0.1.0.tar.gz", sdist_files)

    assert checker.main([str(dir_a), str(dir_b)]) == 0
    captured = capsys.readouterr()
    assert "Package contents check passed" in captured.out


def test_corrupted_archives(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()

    (dir_a / "hqnn_forge-0.1.0-py3-none-any.whl").write_bytes(b"not a valid zip")
    (dir_b / "hqnn_forge-0.1.0-py3-none-any.whl").write_bytes(b"also not a zip")
    (dir_a / "hqnn_forge-0.1.0.tar.gz").write_bytes(b"not a valid gzip")
    (dir_b / "hqnn_forge-0.1.0.tar.gz").write_bytes(b"also not a gzip")

    errors = checker.compare(dir_a, dir_b)
    assert any("Corrupted wheel archive" in e for e in errors)
    assert any("Corrupted sdist archive" in e for e in errors)
