#!/usr/bin/env python3
"""strands-ship machine setup -- Windows-adapted copy.

Patched from the power's ship.py for native Windows:
  - removes the hard-coded "native Windows" block
  - uses Scripts/python.exe (Windows venv layout) instead of bin/python
  - creates ss.cmd + ss.py launcher instead of a shell script
  - relaxes the Python version check to allow 3.14 (best-effort)
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

IS_WIN = platform.system() == "Windows"

HOME = Path(os.environ.get("STRANDS_SHIP_HOME", Path.home() / ".strands-ship"))
# The power kit lives here regardless of where this script runs.
POWER = Path(os.environ.get(
    "STRANDS_SHIP_POWER",
    str(Path.home() / ".kiro" / "powers" / "installed" / "strands-ship"),
))
KIT = POWER / "kit"
REQ = KIT / "project" / "requirements.txt"

# On Windows the interpreter is usually just `python`; add the `py` launcher too.
PYTHONS = ["python3.13", "python3.12", "python3.11", "python3.10", "python3", "python"]
# Relax the upper bound to 14 so we can attempt the install on 3.14.
PY_MIN, PY_MAX = 10, 14


def _py() -> tuple[str | None, str]:
    for name in PYTHONS:
        exe = shutil.which(name)
        if not exe:
            continue
        v = subprocess.run(
            [exe, "-c", "import sys;print('%d.%d'%sys.version_info[:2])"],
            capture_output=True, text=True,
        ).stdout.strip()
        try:
            major, minor = map(int, v.split("."))
        except ValueError:
            continue
        if major == 3 and PY_MIN <= minor <= PY_MAX:
            return exe, v
    # Last resort: try the Windows `py` launcher with explicit minor versions.
    if IS_WIN:
        for minor in (13, 12, 11, 10, 14):
            tag = f"-3.{minor}"
            exe = shutil.which("py")
            if not exe:
                continue
            r = subprocess.run(
                [exe, tag, "-c", "import sys;print('%d.%d'%sys.version_info[:2])"],
                capture_output=True, text=True,
            )
            v = r.stdout.strip()
            try:
                major, mn = map(int, v.split("."))
            except ValueError:
                continue
            if major == 3 and PY_MIN <= mn <= PY_MAX:
                # Return the py launcher with the tag baked into the exe path.
                return f"{exe} {tag}", v
    return None, ""


def _venv_python(venv: Path) -> Path:
    """Return the venv interpreter path for the current platform."""
    if IS_WIN:
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def doctor() -> int:
    rows = []
    add = lambda lvl, what, fix="": rows.append((lvl, what, fix))
    system = platform.system()
    # PATCH: do not block on native Windows; just note it.
    add("OK", f"{system} {platform.machine()}")
    exe, v = _py()
    add("OK", f"Python {v} at {exe}") if exe else add(
        "BLOCK", f"no Python 3.{PY_MIN}-3.{PY_MAX}",
        f"install Python 3.12 (windows: winget install Python.Python.3.12)")
    add("OK", "git") if shutil.which("git") else add("BLOCK", "git missing", "install git")
    add("OK", "uvx (runs the Strands MCP server)") if shutil.which("uvx") else add(
        "WARN", "uvx missing: the strands-agents MCP server in this power will not start",
        "install uv: https://docs.astral.sh/uv/")
    add("OK", "ffmpeg (demo video as mp4)") if shutil.which("ffmpeg") else add(
        "WARN", "ffmpeg missing: the demo video stays .webm (YouTube accepts it)",
        "windows: winget install ffmpeg")
    free = shutil.disk_usage(Path.home()).free / 1e9
    add("OK" if free > 2 else "BLOCK", f"{free:.0f} GB free disk (needs about 0.6 GB)", "" if free > 2 else "free some disk")
    if shutil.which("aws"):
        r = subprocess.run(["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"], capture_output=True, text=True)
        add("OK", "AWS credentials work") if r.returncode == 0 else add(
            "WARN", "AWS credentials not working", "run `aws configure` or `aws sso login` in your own terminal")
    else:
        add("WARN", "AWS CLI not found (optional; boto3 reads ~/.aws or env vars)", "https://aws.amazon.com/cli/")
    for lvl, what, fix in rows:
        print(f"{lvl:5} {what}" + (f"\n      fix: {fix}" if fix else ""))
    blocked = any(r[0] == "BLOCK" for r in rows)
    print("RESULT " + ("BLOCKED" if blocked else "READY"))
    return 1 if blocked else 0


def setup(browser: bool = True) -> int:
    if doctor():
        return 1
    exe, v = _py()
    venv = HOME / "venv"
    HOME.mkdir(parents=True, exist_ok=True)
    py = _venv_python(venv)
    if not py.exists():
        print(f"[1/5] venv with Python {v} at {venv}")
        # `py -3.x` style exe needs splitting; plain exe is a single element.
        exe_parts = exe.split()
        subprocess.run(exe_parts + ["-m", "venv", str(venv)], check=True)
    else:
        print("[1/5] venv exists")
    print("[2/5] pinned packages (Strands Agents SDK + tools, Strands Evals, Strands harness, Strands Shell, boto3, Playwright)")
    subprocess.run([str(py), "-m", "pip", "install", "-q", "--disable-pip-version-check", "-r", str(REQ)], check=True)
    print("[3/5] kit")
    shutil.rmtree(HOME / "kit", ignore_errors=True)
    shutil.copytree(KIT, HOME / "kit", ignore=shutil.ignore_patterns("__pycache__", "results", "_raw"))
    print("[4/5] launcher ~/.strands-ship/bin/ss")
    (HOME / "bin").mkdir(exist_ok=True)
    _write_launcher(py, HOME)
    if browser:
        print("[5/5] headless Chromium for `ss video` (about 150 MB, once)")
        subprocess.run([str(py), "-m", "playwright", "install", "chromium"], check=False)
    else:
        print("[5/5] browser skipped (`ss video` installs it on first use)")
    r = subprocess.run(
        [str(py), "-c", "import strands, strands_evals, strands_harness, strands_shell, boto3; from strands.multiagent import GraphBuilder, Swarm; print('imports ok')"],
        capture_output=True, text=True,
    )
    ok = r.returncode == 0
    (HOME / "state.json").write_text(json.dumps({"python": str(py), "power": str(POWER), "ok": ok}, indent=2) + "\n")
    print(r.stdout.strip() or r.stderr.strip()[-400:])
    print("SETUP " + ("OK: next, in your project folder run the ss launcher" if ok else "FAILED"))
    return 0 if ok else 1


def _write_launcher(py: Path, home: Path) -> None:
    """Write a platform-appropriate `ss` launcher."""
    kit = home / "kit"
    if IS_WIN:
        # ss.py does the real work; ss.cmd is a thin wrapper so it can be called as `ss`.
        ss_py = home / "bin" / "ss.py"
        ss_py.write_text(
            "import sys\n"
            f"sys.path.insert(0, r'{kit}')\n"
            "from ship_kit.cli import main\n"
            "sys.exit(main())\n"
        )
        ss_cmd = home / "bin" / "ss.cmd"
        ss_cmd.write_text(
            "@echo off\n"
            f'"{py}" "%~dp0ss.py" %*\n'
        )
    else:
        ss = home / "bin" / "ss"
        ss.write_text(
            f'#!/bin/sh\nexec "{py}" -c "import sys; sys.path.insert(0, \'{kit}\'); '
            f'from ship_kit.cli import main; sys.exit(main())" "$@"\n'
        )
        ss.chmod(0o755)


def status() -> int:
    st = HOME / "state.json"
    print(st.read_text() if st.exists() else "not set up: run `python ship_win.py setup`")
    return 0


def uninstall(yes: bool) -> int:
    if not HOME.exists():
        print("nothing to remove")
        return 0
    size = sum(p.stat().st_size for p in HOME.rglob("*") if p.is_file()) / 1e6
    if not yes:
        print(f"would remove {HOME} ({size:.0f} MB). Run again with --yes.")
        return 1
    shutil.rmtree(HOME)
    print(f"removed {HOME} ({size:.0f} MB). Your project folders were not touched.")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:] or ["doctor"]
    cmd = args[0]
    sys.exit({
        "doctor": lambda: doctor(),
        "setup": lambda: setup("--no-browser" not in args),
        "status": status,
        "uninstall": lambda: uninstall("--yes" in args),
    }.get(cmd, lambda: (print(__doc__), 2)[1])())
