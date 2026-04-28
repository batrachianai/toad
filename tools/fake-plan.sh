#!/usr/bin/env bash
# Drive a fake orch plan from the shell so you can poke the canon
# PlanExecutionTab without spawning real workers.
#
# Usage (from any project where you'd run `canon .`):
#
#   tools/fake-plan.sh init [slug] [item-count]   # create a fresh plan
#   tools/fake-plan.sh tick [slug]                # advance next item: queued→running, or running→done
#   tools/fake-plan.sh fail [slug]                # mark the running item failed
#   tools/fake-plan.sh ship [slug]                # mark all items done + final SHIP
#   tools/fake-plan.sh stale [slug] [age-sec]     # rewind updatedAt so stale-detection fires (default 600s)
#   tools/fake-plan.sh remove [slug]              # delete plan dir + master.json entry
#
# Defaults: slug=fake-plan-demo, item-count=5, project=$PWD.
# All state lives under $PWD/.orchestrator/ — point canon at the same dir.

set -euo pipefail

CMD="${1:-help}"
SLUG="${2:-fake-plan-demo}"
ARG3="${3:-}"

PROJECT_ROOT="${PROJECT_ROOT:-$PWD}"
ORCH_DIR="$PROJECT_ROOT/.orchestrator"
PLAN_DIR="$ORCH_DIR/plans/$SLUG"
STATE_JSON="$PLAN_DIR/state.json"
MASTER_JSON="$ORCH_DIR/master.json"

py() {
  SLUG="$SLUG" PLAN_DIR="$PLAN_DIR" STATE_JSON="$STATE_JSON" \
    MASTER_JSON="$MASTER_JSON" ORCH_DIR="$ORCH_DIR" \
    python3 -
}

cmd_help() {
  sed -n '2,18p' "$0"
}

cmd_init() {
  local count="${ARG3:-5}"
  mkdir -p "$PLAN_DIR/logs"
  ITEM_COUNT="$count" py <<'PY'
import json, os, datetime
slug = os.environ["SLUG"]
n = int(os.environ.get("ITEM_COUNT") or 5)
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
items = [
    {
        "id": i + 1,
        "description": f"Fake item {i + 1}",
        "deps": [i] if i > 0 else [],
        "status": "queued",
        "workerPid": None,
        "tmuxPane": None,
        "worktree": None,
        "iteration": 0,
        "maxIterations": 3,
        "lastResult": None,
        "reviewStatus": None,
    }
    for i in range(n)
]
state = {
    "version": 1,
    "plan": slug,
    "issueNumber": 999,
    "maxParallelWorkers": 1,
    "mode": "foreground",
    "items": items,
    "finalReview": {"status": "queued", "result": None, "reworkItems": []},
    "startedAt": now,
    "updatedAt": now,
    "status": "running",
}
with open(os.environ["STATE_JSON"], "w", encoding="utf-8") as fh:
    json.dump(state, fh, indent=2)

master_path = os.environ["MASTER_JSON"]
os.makedirs(os.path.dirname(master_path), exist_ok=True)
try:
    with open(master_path, encoding="utf-8") as fh:
        master = json.load(fh)
except (FileNotFoundError, json.JSONDecodeError):
    master = {"version": 1, "plans": []}
plans = [p for p in master.get("plans", []) if p.get("slug") != slug]
plans.append({
    "slug": slug,
    "status": "running",
    "statePath": os.path.relpath(os.environ["STATE_JSON"], os.environ["ORCH_DIR"]),
    "tmuxSession": f"orch-{slug}",
    "worktree": f"worktrees/{slug}",
    "startedAt": now,
    "updatedAt": now,
    "progress": {"total": n, "done": 0, "running": 0, "failed": 0},
})
master["plans"] = plans
with open(master_path, "w", encoding="utf-8") as fh:
    json.dump(master, fh, indent=2)
print(f"init: {slug} with {n} items at {os.environ['PLAN_DIR']}")
PY
}

cmd_mutate() {
  local action="$1"
  ACTION="$action" py <<'PY'
import json, os, datetime
action = os.environ["ACTION"]
state_path = os.environ["STATE_JSON"]
master_path = os.environ["MASTER_JSON"]
slug = os.environ["SLUG"]
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

with open(state_path, encoding="utf-8") as fh:
    state = json.load(fh)
items = state["items"]

if action == "tick":
    running = next((it for it in items if it["status"] == "running"), None)
    if running is not None:
        running["status"] = "done"
        running["lastResult"] = "SHIP"
        running["reviewStatus"] = "passed"
        msg = f"tick: item {running['id']} running→done"
    else:
        nxt = next((it for it in items if it["status"] == "queued"), None)
        if nxt is None:
            msg = "tick: nothing to advance (all done?)"
        else:
            nxt["status"] = "running"
            msg = f"tick: item {nxt['id']} queued→running"
elif action == "fail":
    running = next((it for it in items if it["status"] == "running"), None)
    if running is None:
        msg = "fail: no running item"
    else:
        running["status"] = "failed"
        running["lastResult"] = "REVISE"
        msg = f"fail: item {running['id']} running→failed"
elif action == "ship":
    for it in items:
        if it["status"] != "done":
            it["status"] = "done"
            it["lastResult"] = "SHIP"
            it["reviewStatus"] = "passed"
    state["finalReview"] = {"status": "done", "verdict": "SHIP", "result": "SHIP", "reworkItems": []}
    state["status"] = "completed"
    msg = "ship: all items done, finalReview SHIP"
else:
    raise SystemExit(f"unknown action {action!r}")

state["updatedAt"] = now
# Atomic write so the watcher sees a single rename event.
tmp = state_path + ".tmp"
with open(tmp, "w", encoding="utf-8") as fh:
    json.dump(state, fh, indent=2)
os.replace(tmp, state_path)

with open(master_path, encoding="utf-8") as fh:
    master = json.load(fh)
for entry in master.get("plans", []):
    if entry.get("slug") == slug:
        total = len(items)
        done = sum(1 for it in items if it["status"] == "done")
        running = sum(1 for it in items if it["status"] == "running")
        failed = sum(1 for it in items if it["status"] == "failed")
        entry["progress"] = {"total": total, "done": done, "running": running, "failed": failed}
        entry["updatedAt"] = now
        if action == "ship":
            entry["status"] = "completed"
        break
mtmp = master_path + ".tmp"
with open(mtmp, "w", encoding="utf-8") as fh:
    json.dump(master, fh, indent=2)
os.replace(mtmp, master_path)
print(msg)
PY
}

cmd_stale() {
  local age="${ARG3:-600}"
  AGE="$age" py <<'PY'
import json, os, datetime
age = int(os.environ["AGE"])
slug = os.environ["SLUG"]
master_path = os.environ["MASTER_JSON"]
state_path = os.environ["STATE_JSON"]
old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=age)).strftime("%Y-%m-%dT%H:%M:%SZ")

with open(master_path, encoding="utf-8") as fh:
    master = json.load(fh)
for entry in master.get("plans", []):
    if entry.get("slug") == slug:
        entry["updatedAt"] = old
        entry["status"] = "running"
with open(master_path, "w", encoding="utf-8") as fh:
    json.dump(master, fh, indent=2)

with open(state_path, encoding="utf-8") as fh:
    state = json.load(fh)
state["updatedAt"] = old
with open(state_path, "w", encoding="utf-8") as fh:
    json.dump(state, fh, indent=2)
print(f"stale: rewound updatedAt to {old} ({age}s ago)")
PY
}

cmd_remove() {
  py <<'PY'
import json, os, shutil
slug = os.environ["SLUG"]
plan_dir = os.environ["PLAN_DIR"]
master_path = os.environ["MASTER_JSON"]
if os.path.isdir(plan_dir):
    shutil.rmtree(plan_dir)
try:
    with open(master_path, encoding="utf-8") as fh:
        master = json.load(fh)
    before = len(master.get("plans", []))
    master["plans"] = [p for p in master.get("plans", []) if p.get("slug") != slug]
    with open(master_path, "w", encoding="utf-8") as fh:
        json.dump(master, fh, indent=2)
    removed = before - len(master["plans"])
except FileNotFoundError:
    removed = 0
print(f"remove: deleted plan dir + {removed} master.json entry/entries")
PY
}

case "$CMD" in
  init) cmd_init ;;
  tick) cmd_mutate tick ;;
  fail) cmd_mutate fail ;;
  ship) cmd_mutate ship ;;
  stale) cmd_stale ;;
  remove) cmd_remove ;;
  help | -h | --help) cmd_help ;;
  *)
    echo "unknown command: $CMD" >&2
    cmd_help
    exit 1
    ;;
esac
