from __future__ import annotations

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


def task_to_rows(task: dict) -> list[dict]:
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
            "weight_g": entry["weight"],
            "task_id": task["id"],
        })
    return rows
