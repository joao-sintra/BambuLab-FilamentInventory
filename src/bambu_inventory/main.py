# src/bambu_inventory/main.py
import os
import time
import logging
from dotenv import load_dotenv

from bambu_inventory.state import StateStore
from bambu_inventory.task_mapper import filter_new_terminal_tasks, task_to_rows
from bambu_inventory.bambu_client import BambuClient, AuthExpiredError
from bambu_inventory.sheets_client import SheetsClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bambu_inventory")


def prompt_for_verification_code() -> str:
    return input("Enter the verification code emailed to you: ").strip()


def run_poll_cycle(bambu: BambuClient, sheets: SheetsClient, state: StateStore) -> None:
    try:
        tasks = bambu.get_tasks(limit=20)
    except AuthExpiredError:
        log.warning("Bambu token expired, re-authenticating (may require emailed code)")
        bambu.login(verify_code_prompt=prompt_for_verification_code)
        tasks = bambu.get_tasks(limit=20)

    last_seen_id = state.get_last_seen_id()
    new_tasks = filter_new_terminal_tasks(tasks, last_seen_id)
    if not new_tasks:
        return

    # tasks are returned newest-first; process oldest-first so state
    # advances monotonically and a mid-loop crash re-polls safely
    new_tasks.reverse()

    for task in new_tasks:
        rows = task_to_rows(task)
        if rows:
            sheets.append_rows(rows)
        state.set_last_seen_id(task["id"])
        log.info(f"Logged task {task['id']} ({task['title']}) - {len(rows)} row(s)")


def main() -> None:
    load_dotenv()
    email = os.environ["BAMBU_EMAIL"]
    password = os.environ["BAMBU_PASSWORD"]
    spreadsheet_id = os.environ.get("SPREADSHEET_ID") or None
    poll_interval = int(os.environ.get("POLL_INTERVAL_SEC", "300"))

    bambu = BambuClient(email, password, token_path=".bambu_token.json")
    if not os.path.exists(".bambu_token.json"):
        bambu.login(verify_code_prompt=prompt_for_verification_code)

    sheets = SheetsClient("credentials.json", spreadsheet_id)
    resolved_id = sheets.ensure_spreadsheet()
    if not spreadsheet_id:
        log.info(f"Created new spreadsheet. Save this to .env as SPREADSHEET_ID={resolved_id}")

    state = StateStore("state.json")

    log.info(f"Starting poll loop, interval={poll_interval}s")
    while True:
        try:
            run_poll_cycle(bambu, sheets, state)
        except Exception:
            log.exception("Poll cycle failed, will retry next interval")
        time.sleep(poll_interval)


if __name__ == "__main__":
    main()
