from __future__ import annotations

# NOTE: status strings confirmed from community docs for RUNNING/FINISH/FAILED.
# Verify against a real account (see Task 6 debug-dump step) and extend this
# set if the live API returns other non-terminal states (e.g. "PREPARE",
# "SLICING") or other terminal labels.
RUNNING_STATUSES = {"RUNNING", "PREPARE", "SLICING"}

STATUS_LABELS = {
    "FINISH": "finished",
    "FAILED": "failed",
}


def is_terminal_status(status: str) -> bool:
    return status not in RUNNING_STATUSES


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, "unknown")


def filter_new_terminal_tasks(tasks: list[dict], last_seen_id: str | None) -> list[dict]:
    result = []
    for task in tasks:
        if not is_terminal_status(task["status"]):
            continue
        if last_seen_id is not None and task["id"] <= last_seen_id:
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
