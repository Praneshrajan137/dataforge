#!/usr/bin/env python3
"""Shared cycle-state helper for the four-day, twenty-session automation cycle.

Twenty unattended sessions read and append to the same two JSON files in ``/workspace/cycle``.
Without a single implementation of that, each session hand-rolls its own, and they disagree in
small ways that only surface days later: one drops a key it did not know about, another rewrites
a list it should have appended to, a third writes a BOM that makes the next session's
``json.load`` fail with ``Expecting value: line 1 column 1`` -- which reads as malformed JSON
rather than as an encoding problem.

Three properties matter more than convenience here:

1. **Append, never replace.** ``COVERAGE.json`` and the session list in ``CYCLE.json`` are the
   cycle's memory. A session that rewrites them from scratch silently deletes what earlier
   sessions established, and nothing downstream can tell that happened.
2. **Preserve unknown keys.** A later session must not drop a field it does not recognise. This
   file will be edited across cycles; forward compatibility is cheap here and expensive to
   retrofit.
3. **Write atomically.** A session killed by the fifteen-minute wall mid-write would otherwise
   leave truncated JSON, which fails every subsequent lineage check and destroys the cycle for a
   reason unrelated to the work. Write to a temp file and replace.

Standard library only, deliberately: this runs inside the snapshot before any virtualenv exists.

Usage from a fire::

    python3 scripts/automation/cycle/cycle_state.py show
    python3 scripts/automation/cycle/cycle_state.py verify-lineage
    python3 scripts/automation/cycle/cycle_state.py next-assignment --phase explore --slot 2
    python3 scripts/automation/cycle/cycle_state.py record-session --day 1 --slot 2 \\
        --phase explore --assignment E2 --status OK --artifact FINDINGS/E2.md --summary "..."
    python3 scripts/automation/cycle/cycle_state.py close-question --id Q3 --evidence "..."
    python3 scripts/automation/cycle/cycle_state.py eliminate --hypothesis "..." --evidence "..."
    python3 scripts/automation/cycle/cycle_state.py certify --value true --reason "..."

Every subcommand prints JSON to stdout and exits non-zero on refusal, so a fire can branch on it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CYCLE_DIR = Path(os.environ.get("CYCLE_DIR", "/workspace/cycle"))
WORKSPACE = Path(os.environ.get("WORKSPACE_DIR", "/workspace"))

CYCLE_JSON = CYCLE_DIR / "CYCLE.json"
COVERAGE_JSON = CYCLE_DIR / "COVERAGE.json"

PHASES = ("explore", "plan", "code", "verify")
PHASE_DAY = {"explore": 1, "plan": 2, "code": 3, "verify": 4}
ASSIGNMENTS = {
    "explore": ["E1", "E2", "E3", "E4", "E5"],
    "plan": ["P1", "P2", "P3", "P4", "P5"],
    "code": ["C1", "C2", "C3", "C4", "C5"],
    "verify": ["V1", "V2", "V3", "V4", "V5"],
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8-sig")  # utf-8-sig tolerates a BOM rather than dying on it
    if not raw.strip():
        return {}
    return json.loads(raw)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomic replace. A fire killed mid-write must not leave truncated JSON behind.

    ``fsync`` is BEST EFFORT, not guaranteed. Measured by a D3 session on 2026-09-10: the
    ``/workspace`` stage mount raises ``OSError`` errno 95 (Operation not supported) for
    ``open(path, 'a')`` and for ``os.fsync``. Durability there is the stage's business, not ours,
    and a hard failure here would abort a session for a reason that has nothing to do with its
    work -- which is precisely the class of silent, unrelated failure this pipeline exists to
    avoid. So we ask for the flush and carry on if the mount declines.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(payload, fh, indent=2, sort_keys=False)
            fh.write("\n")
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass  # errno 95 on the stage mount; see docstring
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _md5(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fail(message: str, **extra: Any) -> None:
    print(json.dumps({"ok": False, "error": message, **extra}, indent=2))
    raise SystemExit(1)


def _ok(**payload: Any) -> None:
    print(json.dumps({"ok": True, **payload}, indent=2))


# --------------------------------------------------------------------------------------------


def cmd_show(_args: argparse.Namespace) -> None:
    cycle = _read_json(CYCLE_JSON)
    coverage = _read_json(COVERAGE_JSON)
    _ok(
        cycle_id=cycle.get("cycle_id"),
        certified=cycle.get("certified"),
        sessions=cycle.get("sessions", []),
        assignments_complete=coverage.get("assignments_complete", []),
        open_question_count=len(coverage.get("questions_open", [])),
        closed_question_count=len(coverage.get("questions_closed", [])),
        eliminated_count=len(coverage.get("hypotheses_eliminated", [])),
    )


def cmd_verify_lineage(args: argparse.Namespace) -> None:
    """Refuse loudly rather than let a session work from mismatched inputs.

    The failure this prevents is silent: a day whose sessions all died leaves the previous day's
    artifacts in place, and a successor reads them as current and reports success.
    """
    cycle = _read_json(CYCLE_JSON)
    if not cycle:
        _fail("CYCLE.json missing or empty; the cycle was never started")

    task = WORKSPACE / "TASK.md"
    snap = WORKSPACE / "dataforge-snapshot.tar.gz"

    problems: list[str] = []
    task_sha = _sha256(task)
    snap_md5 = _md5(snap)

    if task_sha is None:
        problems.append("TASK.md is missing")
    elif cycle.get("task_sha256") and task_sha != cycle["task_sha256"]:
        problems.append("TASK.md sha256 does not match CYCLE.json")

    if snap_md5 is None:
        problems.append("snapshot is missing")
    elif cycle.get("snapshot_md5") and snap_md5 != cycle["snapshot_md5"]:
        problems.append("snapshot md5 does not match CYCLE.json")

    # A phase may only run if the phase it depends on actually produced completed sessions.
    if args.phase:
        needed = {"plan": "explore", "code": "plan", "verify": "code"}.get(args.phase)
        if needed:
            done = [
                s
                for s in cycle.get("sessions", [])
                if s.get("phase") == needed and s.get("status") == "OK"
            ]
            if not done:
                problems.append(f"phase '{args.phase}' requires completed '{needed}' sessions; none recorded")

    if problems:
        _fail("; ".join(problems), cycle_id=cycle.get("cycle_id"))

    _ok(cycle_id=cycle.get("cycle_id"), task_sha256=task_sha, snapshot_md5=snap_md5)


def cmd_next_assignment(args: argparse.Namespace) -> None:
    """Fixed assignment by slot, with a sequential fallback to the earliest incomplete one.

    Sessions are 45 minutes apart and never overlap, so a queue-style fallback is safe here; the
    risk it removes is a dead session leaving its assignment permanently unowned.
    """
    if args.phase not in PHASES:
        _fail(f"unknown phase '{args.phase}'")
    coverage = _read_json(COVERAGE_JSON)
    complete = set(coverage.get("assignments_complete", []))
    order = ASSIGNMENTS[args.phase]

    preferred = None
    if args.slot and 1 <= args.slot <= len(order):
        preferred = order[args.slot - 1]

    if preferred and preferred not in complete:
        _ok(assignment=preferred, reason="slot assignment", slot=args.slot)
        return

    for candidate in order:
        if candidate not in complete:
            _ok(
                assignment=candidate,
                reason="fallback: slot assignment already complete",
                slot=args.slot,
                preferred=preferred,
            )
            return

    # Everything is done. Do not invent work; say so and let the prompt's guidance apply.
    _ok(
        assignment=None,
        reason="all assignments for this phase are complete; deepen the weakest artifact or "
        "attack the highest-ranked open question, and say so in JOURNAL.md",
        slot=args.slot,
    )


def cmd_record_session(args: argparse.Namespace) -> None:
    cycle = _read_json(CYCLE_JSON)
    if not cycle:
        _fail("CYCLE.json missing; refusing to create one from a session")

    sessions = list(cycle.get("sessions", []))
    sessions.append(
        {
            "day": args.day,
            "slot": args.slot,
            "phase": args.phase,
            "assignment": args.assignment,
            "status": args.status,
            "artifact": args.artifact,
            "summary": args.summary,
            "finished_utc": _now(),
        }
    )
    cycle["sessions"] = sessions
    _write_json(CYCLE_JSON, cycle)

    # Only a successful session marks its assignment complete. A FAILED one must leave the
    # assignment claimable, otherwise the fallback cannot recover the work.
    coverage = _read_json(COVERAGE_JSON)
    if args.status == "OK" and args.assignment:
        complete = list(coverage.get("assignments_complete", []))
        if args.assignment not in complete:
            complete.append(args.assignment)
        coverage["assignments_complete"] = complete
    if args.files_read:
        read = list(coverage.get("files_read", []))
        for f in args.files_read.split(","):
            f = f.strip()
            if f and f not in read:
                read.append(f)
        coverage["files_read"] = read
    coverage["updated_utc"] = _now()
    _write_json(COVERAGE_JSON, coverage)

    _ok(recorded=sessions[-1], assignments_complete=coverage.get("assignments_complete", []))


def cmd_close_question(args: argparse.Namespace) -> None:
    """A closed question must carry the evidence that closed it, or it is not closed."""
    if not args.evidence.strip():
        _fail("refusing to close a question with no evidence")
    coverage = _read_json(COVERAGE_JSON)
    closed = list(coverage.get("questions_closed", []))
    closed.append({"id": args.id, "question": args.question, "evidence": args.evidence, "at": _now()})
    coverage["questions_closed"] = closed
    coverage["questions_open"] = [
        q for q in coverage.get("questions_open", []) if q.get("id") != args.id
    ]
    coverage["updated_utc"] = _now()
    _write_json(COVERAGE_JSON, coverage)
    _ok(closed=closed[-1])


def cmd_open_question(args: argparse.Namespace) -> None:
    coverage = _read_json(COVERAGE_JSON)
    open_qs = list(coverage.get("questions_open", []))
    if any(q.get("id") == args.id for q in open_qs):
        _fail(f"question id '{args.id}' already open")
    open_qs.append({"id": args.id, "question": args.question, "rank": args.rank, "at": _now()})
    coverage["questions_open"] = open_qs
    coverage["updated_utc"] = _now()
    _write_json(COVERAGE_JSON, coverage)
    _ok(opened=open_qs[-1])


def cmd_eliminate(args: argparse.Namespace) -> None:
    """Record a negative result.

    Eliminated hypotheses are expensive to establish and free for a memoryless successor to get
    wrong, so they are recorded with the same rigour as positive findings.
    """
    if not args.evidence.strip():
        _fail("refusing to record an elimination with no evidence")
    coverage = _read_json(COVERAGE_JSON)
    gone = list(coverage.get("hypotheses_eliminated", []))
    gone.append({"hypothesis": args.hypothesis, "evidence": args.evidence, "at": _now()})
    coverage["hypotheses_eliminated"] = gone
    coverage["updated_utc"] = _now()
    _write_json(COVERAGE_JSON, coverage)
    _ok(eliminated=gone[-1])


def cmd_certify(args: argparse.Namespace) -> None:
    cycle = _read_json(CYCLE_JSON)
    if not cycle:
        _fail("CYCLE.json missing")
    value = args.value.lower() == "true"
    if value and not args.reason.strip():
        _fail("refusing to certify without a stated reason")
    cycle["certified"] = value
    cycle["certified_utc"] = _now()
    cycle["certification_reason"] = args.reason
    _write_json(CYCLE_JSON, cycle)
    _ok(certified=value, reason=args.reason)


def cmd_slot_now(_args: argparse.Namespace) -> None:
    """Report the current IST slot.

    UTC would mislead: 00:30 IST is 19:00 UTC on the PREVIOUS day, so a naive UTC weekday lookup
    reports the wrong day for every slot in this window.
    """
    try:
        out = subprocess.run(
            ["date", "+%Y-%m-%d %H:%M %a"],
            env={**os.environ, "TZ": "Asia/Kolkata"},
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception as exc:  # noqa: BLE001 - report, never guess a slot
        _fail(f"could not determine local time: {exc}")
        return

    date_part, hhmm, weekday = out.rsplit(" ", 2)[0], out.split(" ")[1], out.split(" ")[2]
    hours, minutes = (int(x) for x in hhmm.split(":"))
    now_min = hours * 60 + minutes
    slots = [(1, 30), (2, 75), (3, 120), (4, 165), (5, 210)]  # 00:30, 01:15, 02:00, 02:45, 03:30
    slot = None
    for number, start in slots:
        if now_min >= start - 5:
            slot = number
    _ok(local=out, date=date_part, weekday=weekday, slot=slot)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("show").set_defaults(func=cmd_show)
    sub.add_parser("slot-now").set_defaults(func=cmd_slot_now)

    p = sub.add_parser("verify-lineage")
    p.add_argument("--phase", choices=PHASES)
    p.set_defaults(func=cmd_verify_lineage)

    p = sub.add_parser("next-assignment")
    p.add_argument("--phase", required=True)
    p.add_argument("--slot", type=int)
    p.set_defaults(func=cmd_next_assignment)

    p = sub.add_parser("record-session")
    p.add_argument("--day", type=int, required=True)
    p.add_argument("--slot", type=int, required=True)
    p.add_argument("--phase", required=True, choices=PHASES)
    p.add_argument("--assignment", required=True)
    p.add_argument("--status", required=True, choices=["OK", "FAILED"])
    p.add_argument("--artifact", default="")
    p.add_argument("--summary", default="")
    p.add_argument("--files-read", default="")
    p.set_defaults(func=cmd_record_session)

    p = sub.add_parser("open-question")
    p.add_argument("--id", required=True)
    p.add_argument("--question", required=True)
    p.add_argument("--rank", type=int, default=0)
    p.set_defaults(func=cmd_open_question)

    p = sub.add_parser("close-question")
    p.add_argument("--id", required=True)
    p.add_argument("--question", default="")
    p.add_argument("--evidence", required=True)
    p.set_defaults(func=cmd_close_question)

    p = sub.add_parser("eliminate")
    p.add_argument("--hypothesis", required=True)
    p.add_argument("--evidence", required=True)
    p.set_defaults(func=cmd_eliminate)

    p = sub.add_parser("certify")
    p.add_argument("--value", required=True, choices=["true", "false"])
    p.add_argument("--reason", default="")
    p.set_defaults(func=cmd_certify)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
