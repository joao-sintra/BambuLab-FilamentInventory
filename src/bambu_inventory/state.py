import json
import os


class StateStore:
    def __init__(self, path: str):
        self._path = path

    def get_last_seen_id(self) -> str | None:
        if not os.path.exists(self._path):
            return None
        with open(self._path, "r") as f:
            data = json.load(f)
        return data.get("last_seen_task_id")

    def set_last_seen_id(self, task_id: str) -> None:
        with open(self._path, "w") as f:
            json.dump({"last_seen_task_id": task_id}, f)
