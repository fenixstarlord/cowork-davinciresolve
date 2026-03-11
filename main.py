#!/usr/bin/env python3
"""
Bootstrap script: sets up venv, installs dependencies, builds the vector
index if needed, then launches the chat.
"""

import os
import platform
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(ROOT, ".venv")
_bin = "Scripts" if platform.system() == "Windows" else "bin"
VENV_PYTHON = os.path.join(VENV_DIR, _bin, "python")
REQUIREMENTS = os.path.join(ROOT, "requirements.txt")
VECTORSTORE = os.path.join(ROOT, "vectorstore")
MARKER = os.path.join(VENV_DIR, ".deps_installed")


def run(cmd, **kwargs):
    print(f"  > {' '.join(cmd)}")
    subprocess.check_call(cmd, **kwargs)


def ensure_venv():
    if not os.path.exists(VENV_PYTHON):
        print("[1/3] Creating virtual environment...")
        run([sys.executable, "-m", "venv", VENV_DIR])
    else:
        print("[1/3] Virtual environment exists.")


def ensure_deps():
    # Re-install if requirements.txt is newer than our marker
    needs_install = not os.path.exists(MARKER)
    if not needs_install:
        needs_install = os.path.getmtime(REQUIREMENTS) > os.path.getmtime(MARKER)

    if needs_install:
        print("[2/3] Installing dependencies...")
        run([VENV_PYTHON, "-m", "pip", "install", "--upgrade", "pip", "-q"])
        run([VENV_PYTHON, "-m", "pip", "install", "-r", REQUIREMENTS, "-q"])
        open(MARKER, "w").close()
    else:
        print("[2/3] Dependencies up to date.")


def ensure_index():
    # Check if vectorstore has content (not just an empty dir)
    has_index = os.path.exists(VECTORSTORE) and any(
        f for f in os.listdir(VECTORSTORE) if not f.startswith(".")
    )
    if not has_index:
        print("[3/3] Building vector index (first run)...")
        run([VENV_PYTHON, "-m", "src.ingest"], cwd=ROOT)
    else:
        print("[3/3] Vector index exists.")


def launch_chat():
    print("\nStarting chat...\n")
    os.execv(VENV_PYTHON, [VENV_PYTHON, "-m", "src.main"] + sys.argv[1:])


if __name__ == "__main__":
    ensure_venv()
    ensure_deps()
    ensure_index()
    launch_chat()
