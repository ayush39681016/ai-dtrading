"""
auto_push.py — Auto GitHub Sync
Periodically commits and pushes runtime data to GitHub.
Syncs: trades.csv, runtime_status.json, config.json
"""

import subprocess
import time
import os
import sys
from datetime import datetime

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
SYNC_FILES = ["trades.csv", "runtime_status.json", "config.json"]
PUSH_INTERVAL_MINUTES = 15  # How often to push (adjustable)


def run_git(cmd, cwd=REPO_DIR):
    """Run a git command and return (success, output)."""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0, result.stdout.strip()
    except Exception as e:
        return False, str(e)


def has_changes():
    """Check if any tracked sync files have changed."""
    ok, output = run_git(["git", "status", "--porcelain"])
    if not ok:
        return False
    for line in output.splitlines():
        for f in SYNC_FILES:
            if f in line:
                return True
    return False


def push_changes():
    """Stage, commit, and push sync files."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Stage only the sync files
    for f in SYNC_FILES:
        filepath = os.path.join(REPO_DIR, f)
        if os.path.exists(filepath):
            run_git(["git", "add", f])

    if not has_changes():
        print(f"[{timestamp}] No changes to push.", flush=True)
        return False

    # Commit
    msg = f"auto: sync trading data ({timestamp})"
    ok, out = run_git(["git", "commit", "-m", msg])
    if not ok:
        print(f"[{timestamp}] Commit failed: {out}", flush=True)
        return False

    # Push
    ok, out = run_git(["git", "push", "origin", "main"])
    if ok:
        print(f"[{timestamp}] Pushed to GitHub successfully.", flush=True)
        return True
    else:
        print(f"[{timestamp}] Push failed: {out}", flush=True)
        return False


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    interval = PUSH_INTERVAL_MINUTES * 60
    print("=== AUTO GITHUB PUSH STARTED ===", flush=True)
    print(f"  Repo: {REPO_DIR}", flush=True)
    print(f"  Sync files: {', '.join(SYNC_FILES)}", flush=True)
    print(f"  Interval: every {PUSH_INTERVAL_MINUTES} minutes", flush=True)
    print("-" * 40, flush=True)

    while True:
        try:
            push_changes()
        except Exception as e:
            print(f"[!] Auto-push error: {e}", flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
