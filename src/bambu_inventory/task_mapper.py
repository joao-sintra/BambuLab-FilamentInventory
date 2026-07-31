from __future__ import annotations

# NOTE: status strings confirmed from community docs for RUNNING/FINISH/FAILED.
# This is a whitelist by design: only statuses confirmed terminal are treated
# as terminal. Any unrecognized/unforeseen status (e.g. "PAUSE", "HEATING")
# is treated as non-terminal and skipped rather than logged and advanced
# past - misclassifying an unknown intermediate status as terminal would
# permanently exclude the print's real completion row via the last_seen_id
# dedup check once the task actually finishes. Verify unrecognized statuses
# against a real account (see README's debug-dump step) and add them here
# once confirmed terminal.
TERMINAL_STATUSES = {"FINISH", "FAILED"}

STATUS_LABELS = {
    "FINISH": "finished",
    "FAILED": "failed",
}


def is_terminal_status(status: str) -> bool:
    return status in TERMINAL_STATUSES


def status_label(status: str) -> str:
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
