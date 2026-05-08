#!/usr/bin/env python
import argparse
import shutil
import subprocess

from concurrent.futures import as_completed
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def freeze(python_version: str, requirement: Path) -> str:
    print(f"🥶 Freezing Python {python_version} {requirement.stem}...", flush=True)

    python_bin = shutil.which(f"python{python_version}")
    if python_bin is None:
        return f"Unable to find Python{python_version}"

    python_bin = Path(python_bin)

    repo_root = requirement.parent.parent
    venv_path = repo_root / ".venvs" / f"freezer-{requirement.stem}-{python_version}"
    venv_python = venv_path / "bin" / "python"
    constraints = repo_root / "requirements" / f"{requirement.stem}-constraints.txt"
    freeze_file = repo_root / "requirements" / f"{requirement.stem}-{python_version}.txt"

    # Create a fresh virtual environment
    subprocess.check_output([python_bin, "-m", "venv", "--clear", venv_path])
    subprocess.check_output([venv_python, "-m", "pip", "install", "--upgrade", "pip"])

    constraint_args = []
    if constraints.is_file():
        constraint_args = ["--constraint", constraints]

    # Install requirements
    subprocess.check_output(
        [
            venv_python,
            "-m",
            "pip",
            "--no-cache-dir",
            "install",
            "--requirement",
            requirement,
            *constraint_args,
        ]
    )

    # Generate a freeze file
    result = subprocess.run([venv_python, "-m", "pip", "freeze"], check=True, capture_output=True)
    freeze_file.write_bytes(result.stdout)

    return f"✅ {requirement.stem}-{python_version} complete"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-versions", default="3.10,3.12,3.13,3.14")
    parser.add_argument("-r", "--requirement", default="requirements")

    return parser.parse_args()


def sort_versions(versions: str) -> list[str]:
    def list_of_parts(items):
        return [int(n) for n in items.split(".")]

    stripped_versions = [version.strip() for version in versions.split(",")]

    return sorted(stripped_versions, key=list_of_parts)


def main():
    args = parse_args()
    file = Path(__file__)
    repo_root = file.parent.parent
    requirements = list(repo_root.joinpath(args.requirement).glob("*.in"))
    python_versions = sort_versions(args.python_versions)
    workers = len(requirements) * len(python_versions)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(freeze, py_ver, req)
            for req in requirements
            for py_ver in python_versions  # noformat
        ]
    for future in as_completed(futures):
        print(future.result())


if __name__ == "__main__":
    main()
