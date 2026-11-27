#!/usr/bin/env python3
"""Counting lock for heavy jobs on the Mac Studio (INF-1983 D37).

A slot is the directory <dir>/slot-<i>, created with os.mkdir (atomic) and holding
owner.json {id, pid, repo, run_url, acquired_at}. A slot whose pid is not alive is free.

  lock.py acquire --dir D --slots 2 --timeout-minutes N --owner JSON   prints slot=<i>
  lock.py release --dir D --slot I --owner-id ID
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import time


STALE_OWNERLESS_SECONDS = 60


def pid_alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (TypeError, ValueError, OverflowError):
        return False
    return True


def runner_worker_pid() -> int:
    """Nearest ancestor process named Runner.Worker, else this process's parent."""
    pid = os.getppid()
    seen = set()
    while pid > 1 and pid not in seen:
        seen.add(pid)
        out = subprocess.run(
            ["ps", "-o", "ppid=,comm=", "-p", str(pid)], capture_output=True, text=True
        ).stdout.strip()
        if not out:
            break
        ppid, _, comm = out.partition(" ")
        if os.path.basename(comm.strip()) == "Runner.Worker":
            return pid
        try:
            pid = int(ppid)
        except ValueError:
            break
    return os.getppid()


def read_owner(slot_dir: str):
    try:
        with open(os.path.join(slot_dir, "owner.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def remove_slot(slot_dir: str) -> None:
    try:
        os.unlink(os.path.join(slot_dir, "owner.json"))
    except OSError:
        pass
    try:
        os.rmdir(slot_dir)
    except OSError:
        pass


def try_acquire(lock_dir: str, slots: int, owner: dict):
    """Return the slot index taken, or None. Prints each busy holder to stderr."""
    for i in range(slots):
        slot_dir = os.path.join(lock_dir, f"slot-{i}")
        try:
            os.mkdir(slot_dir)
        except FileExistsError:
            held = read_owner(slot_dir)
            if held is None:
                try:
                    stale = time.time() - os.stat(slot_dir).st_mtime > STALE_OWNERLESS_SECONDS
                except OSError:
                    stale = False
            else:
                stale = not pid_alive(held.get("pid"))
            if stale:
                remove_slot(slot_dir)
                try:
                    os.mkdir(slot_dir)
                except FileExistsError:
                    continue
            else:
                who = held.get("id", "?") if held else "(starting)"
                url = held.get("run_url", "") if held else ""
                print(f"slot {i} busy: {who} {url}".rstrip(), file=sys.stderr)
                continue
        with open(os.path.join(slot_dir, "owner.json"), "w") as f:
            json.dump(owner, f)
        return i
    return None


def cmd_acquire(args) -> int:
    owner = json.loads(args.owner)
    owner.setdefault("pid", runner_worker_pid())
    owner.setdefault(
        "acquired_at", datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    )
    os.makedirs(args.dir, exist_ok=True)
    deadline = time.monotonic() + args.timeout_minutes * 60
    while True:
        slot = try_acquire(args.dir, args.slots, owner)
        if slot is not None:
            print(f"slot={slot}")
            return 0
        if time.monotonic() >= deadline:
            minutes = f"{args.timeout_minutes:g}"
            print(f"no Studio slot in {minutes} min", file=sys.stderr)
            return 1
        time.sleep(args.poll_seconds)


def cmd_release(args) -> int:
    slot_dir = os.path.join(args.dir, f"slot-{args.slot}")
    held = read_owner(slot_dir)
    if held is not None and held.get("id") == args.owner_id:
        remove_slot(slot_dir)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("acquire")
    a.add_argument("--dir", required=True)
    a.add_argument("--slots", type=int, default=2)
    a.add_argument("--timeout-minutes", type=float, default=120)
    a.add_argument("--owner", required=True)
    a.add_argument("--poll-seconds", type=float, default=15)
    a.set_defaults(fn=cmd_acquire)
    r = sub.add_parser("release")
    r.add_argument("--dir", required=True)
    r.add_argument("--slot", type=int, required=True)
    r.add_argument("--owner-id", required=True)
    r.set_defaults(fn=cmd_release)
    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
