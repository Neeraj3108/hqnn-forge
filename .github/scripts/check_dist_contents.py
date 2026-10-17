"""Compare package distributions built with different backend versions.

Verifies that file manifests and package metadata match between two build outputs,
ignoring only the Generator line in METADATA and PKG-INFO.
"""

from __future__ import annotations

import difflib
import sys
import tarfile
import zipfile
from pathlib import Path


def _filter_metadata(lines: list[str]) -> list[str]:
    """Filter out lines that are expected to differ across backend versions."""
    return [line for line in lines if not line.startswith("Generator:")]


def compare_wheels(wheel_a: Path, wheel_b: Path) -> list[str]:
    """Compare file manifests and METADATA of two wheel archives."""
    errors: list[str] = []
    if wheel_a.name != wheel_b.name:
        errors.append(f"Wheel filenames differ: {wheel_a.name!r} vs {wheel_b.name!r}")

    try:
        with zipfile.ZipFile(wheel_a) as za, zipfile.ZipFile(wheel_b) as zb:
            names_a = sorted(za.namelist())
            names_b = sorted(zb.namelist())
            if names_a != names_b:
                only_a = [n for n in names_a if n not in names_b]
                only_b = [n for n in names_b if n not in names_a]
                msg = "Wheel file lists differ:"
                if only_a:
                    msg += f"\n  Only in {wheel_a.parent.name}: {only_a}"
                if only_b:
                    msg += f"\n  Only in {wheel_b.parent.name}: {only_b}"
                errors.append(msg)

            meta_a_candidates = [n for n in names_a if n.endswith(".dist-info/METADATA")]
            meta_b_candidates = [n for n in names_b if n.endswith(".dist-info/METADATA")]

            if not meta_a_candidates:
                errors.append(f"Missing .dist-info/METADATA in wheel {wheel_a.name}")
            elif len(meta_a_candidates) > 1:
                errors.append(
                    f"Ambiguous: multiple METADATA files in {wheel_a.name}: {meta_a_candidates}"
                )

            if not meta_b_candidates:
                errors.append(f"Missing .dist-info/METADATA in wheel {wheel_b.name}")
            elif len(meta_b_candidates) > 1:
                errors.append(
                    f"Ambiguous: multiple METADATA files in {wheel_b.name}: {meta_b_candidates}"
                )

            if len(meta_a_candidates) == 1 and len(meta_b_candidates) == 1:
                meta_a = _filter_metadata(
                    za.read(meta_a_candidates[0]).decode("utf-8").splitlines()
                )
                meta_b = _filter_metadata(
                    zb.read(meta_b_candidates[0]).decode("utf-8").splitlines()
                )
                if meta_a != meta_b:
                    diff = "\n".join(
                        difflib.unified_diff(
                            meta_a,
                            meta_b,
                            fromfile=f"{wheel_a.parent.name}/{meta_a_candidates[0]}",
                            tofile=f"{wheel_b.parent.name}/{meta_b_candidates[0]}",
                            lineterm="",
                        )
                    )
                    errors.append(f"Wheel METADATA differs (excluding Generator line):\n{diff}")
    except zipfile.BadZipFile as exc:
        errors.append(f"Corrupted wheel archive: {exc}")

    return errors


def compare_sdists(sdist_a: Path, sdist_b: Path) -> list[str]:
    """Compare file manifests and PKG-INFO of two source distribution archives."""
    errors: list[str] = []
    if sdist_a.name != sdist_b.name:
        errors.append(f"Sdist filenames differ: {sdist_a.name!r} vs {sdist_b.name!r}")

    try:
        with tarfile.open(sdist_a, "r:gz") as ta, tarfile.open(sdist_b, "r:gz") as tb:
            names_a = sorted(ta.getnames())
            names_b = sorted(tb.getnames())
            if names_a != names_b:
                only_a = [n for n in names_a if n not in names_b]
                only_b = [n for n in names_b if n not in names_a]
                msg = "Sdist file lists differ:"
                if only_a:
                    msg += f"\n  Only in {sdist_a.parent.name}: {only_a}"
                if only_b:
                    msg += f"\n  Only in {sdist_b.parent.name}: {only_b}"
                errors.append(msg)

            pkg_a_candidates = [n for n in names_a if n == "PKG-INFO" or n.endswith("/PKG-INFO")]
            pkg_b_candidates = [n for n in names_b if n == "PKG-INFO" or n.endswith("/PKG-INFO")]

            if not pkg_a_candidates:
                errors.append(f"Missing PKG-INFO in sdist {sdist_a.name}")
            elif len(pkg_a_candidates) > 1:
                errors.append(
                    f"Ambiguous: multiple PKG-INFO files in {sdist_a.name}: {pkg_a_candidates}"
                )

            if not pkg_b_candidates:
                errors.append(f"Missing PKG-INFO in sdist {sdist_b.name}")
            elif len(pkg_b_candidates) > 1:
                errors.append(
                    f"Ambiguous: multiple PKG-INFO files in {sdist_b.name}: {pkg_b_candidates}"
                )

            if len(pkg_a_candidates) == 1 and len(pkg_b_candidates) == 1:
                f_a = ta.extractfile(pkg_a_candidates[0])
                f_b = tb.extractfile(pkg_b_candidates[0])
                if f_a is None or f_b is None:
                    errors.append("Failed to extract PKG-INFO from sdist archive")
                else:
                    meta_a = _filter_metadata(f_a.read().decode("utf-8").splitlines())
                    meta_b = _filter_metadata(f_b.read().decode("utf-8").splitlines())
                    if meta_a != meta_b:
                        diff = "\n".join(
                            difflib.unified_diff(
                                meta_a,
                                meta_b,
                                fromfile=f"{sdist_a.parent.name}/{pkg_a_candidates[0]}",
                                tofile=f"{sdist_b.parent.name}/{pkg_b_candidates[0]}",
                                lineterm="",
                            )
                        )
                        errors.append(
                            f"Sdist PKG-INFO differs (excluding Generator line):\n{diff}"
                        )
    except (tarfile.TarError, OSError) as exc:
        errors.append(f"Corrupted sdist archive: {exc}")

    return errors


def compare(dir_a: Path, dir_b: Path) -> list[str]:
    """Compare distributions in two directories."""
    errors: list[str] = []

    if not dir_a.is_dir():
        return [f"Directory not found: {dir_a}"]
    if not dir_b.is_dir():
        return [f"Directory not found: {dir_b}"]

    wheels_a = sorted(dir_a.glob("*.whl"))
    wheels_b = sorted(dir_b.glob("*.whl"))
    sdists_a = sorted(dir_a.glob("*.tar.gz"))
    sdists_b = sorted(dir_b.glob("*.tar.gz"))

    if not wheels_a:
        errors.append(f"Missing wheel archive in {dir_a}")
    elif len(wheels_a) > 1:
        errors.append(f"Ambiguous: found multiple wheels in {dir_a}: {[w.name for w in wheels_a]}")

    if not wheels_b:
        errors.append(f"Missing wheel archive in {dir_b}")
    elif len(wheels_b) > 1:
        errors.append(f"Ambiguous: found multiple wheels in {dir_b}: {[w.name for w in wheels_b]}")

    if not sdists_a:
        errors.append(f"Missing sdist archive in {dir_a}")
    elif len(sdists_a) > 1:
        errors.append(f"Ambiguous: found multiple sdists in {dir_a}: {[s.name for s in sdists_a]}")

    if not sdists_b:
        errors.append(f"Missing sdist archive in {dir_b}")
    elif len(sdists_b) > 1:
        errors.append(f"Ambiguous: found multiple sdists in {dir_b}: {[s.name for s in sdists_b]}")

    # If basic archive resolution succeeded, compare contents
    if len(wheels_a) == 1 and len(wheels_b) == 1:
        errors.extend(compare_wheels(wheels_a[0], wheels_b[0]))

    if len(sdists_a) == 1 and len(sdists_b) == 1:
        errors.extend(compare_sdists(sdists_a[0], sdists_b[0]))

    return errors


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        print("Usage: check_dist_contents.py <dir_a> <dir_b>", file=sys.stderr)
        return 2

    errors = compare(Path(args[0]), Path(args[1]))
    for err in errors:
        print(f"::error::{err}", file=sys.stderr)

    if not errors:
        print("Package contents check passed: wheel and sdist files and metadata match.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
