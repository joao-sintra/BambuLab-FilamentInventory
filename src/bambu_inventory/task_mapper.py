from __future__ import annotations

from datetime import datetime

# NOTE: status is an integer code, confirmed against a real account (not the
# string codes some community docs describe). Confirmed so far: 2 = finished
# successfully, 3 = user-cancelled/stopped. This is a whitelist by design:
# only statuses confirmed terminal are treated as terminal. Any
# unrecognized/unforeseen status (e.g. a genuine print-error code, or an
# in-progress code) is treated as non-terminal and skipped rather than
# logged and advanced past - misclassifying an unknown status as terminal
# would permanently exclude the print's real completion row via the
# last_seen_id dedup check once the task actually finishes. Verify
# unrecognized statuses against your account (see README's debug-dump step)
# and add them here once confirmed.
TERMINAL_STATUSES = {2, 3}

STATUS_LABELS = {
    2: "finished",
    3: "cancelled",
}


def is_terminal_status(status: int) -> bool:
    return status in TERMINAL_STATUSES


def status_label(status: int) -> str:
    return STATUS_LABELS.get(status, "unknown")


def filter_new_terminal_tasks(tasks: list[dict], last_seen_id: str | None) -> list[dict]:
    result = []
    for task in tasks:
        if not is_terminal_status(task["status"]):
            continue
        if last_seen_id is not None and int(task["id"]) <= int(last_seen_id):
            continue
        result.append(task)
    return result


def _completion_ratio(task: dict) -> float:
    # amsDetailMapping[].weight and costTime are the slicer's FULL planned
    # values regardless of cancellation (confirmed: a cancelled task's
    # costTime is far larger than its actual endTime-startTime elapsed
    # duration). For anything that didn't finish successfully, scale the
    # planned weight down by how much of the planned time actually elapsed,
    # so a print stopped halfway doesn't register a full print's worth of
    # wasted filament.
    if status_label(task["status"]) == "finished":
        return 1.0

    cost_time = task.get("costTime") or 0
    if cost_time <= 0:
        return 1.0

    try:
        start = datetime.fromisoformat(task["startTime"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(task["endTime"].replace("Z", "+00:00"))
    except (KeyError, ValueError, AttributeError):
        return 1.0

    elapsed = (end - start).total_seconds()
    ratio = elapsed / cost_time
    return max(0.0, min(1.0, ratio))


def task_to_rows(task: dict) -> list[dict]:
    ratio = _completion_ratio(task)
    rows = []
    for entry in task.get("amsDetailMapping", []):
        rows.append({
            "date": task["startTime"],
            "print_name": task["title"],
            "printer": task["deviceName"],
            "status": status_label(task["status"]),
            "duration_min": task["costTime"] // 60,
            "ams_slot": f'{entry["amsId"]}-{entry["slotId"]}',
            "filament_type": entry["filamentType"],
            "colour_hex": entry["targetColor"],
            "weight_g": round(entry["weight"] * ratio, 2),
            "task_id": task["id"],
        })
    return rows
