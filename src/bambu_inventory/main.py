# src/bambu_inventory/main.py
import os
import time
import logging
from dotenv import load_dotenv

from bambu_inventory.state import StateStore
from bambu_inventory.task_mapper import filter_new_terminal_tasks, task_to_rows
from bambu_inventory.bambu_client import BambuClient, AuthExpiredError
from bambu_inventory.local_sheet import LocalSheetWriter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bambu_inventory")


def prompt_for_verification_code() -> str:
    return input("Enter the verification code emailed to you: ").strip()


def run_poll_cycle(bambu: BambuClient, sheet: LocalSheetWriter, state: StateStore) -> None:
    try:
        tasks = bambu.get_tasks(limit=20)
    except AuthExpiredError:
        log.warning("Bambu token expired, attempting refresh")
        if not bambu.refresh():
            if bambu._password:
                log.warning("Refresh failed, re-authenticating (may require emailed code)")
                bambu.login(verify_code_prompt=prompt_for_verification_code)
            else:
                log.error(
                    "Refresh failed and no BAMBU_PASSWORD configured for interactive "
                    "re-login. Manually re-extract a token as described in the README's "
                    "'Google/SSO accounts' section and save it to .bambu_token.json."
                )
                return
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
            sheet.append_rows(rows)
        state.set_last_seen_id(task["id"])
        log.info(f"Logged task {task['id']} ({task['title']}) - {len(rows)} row(s)")


def main() -> None:
    load_dotenv()
    email = os.environ["BAMBU_EMAIL"]
    password = os.environ.get("BAMBU_PASSWORD", "")
    output_path = os.environ.get("OUTPUT_XLSX_PATH", "filament_inventory.xlsx")
    poll_interval = int(os.environ.get("POLL_INTERVAL_SEC", "300"))

    bambu = BambuClient(email, password, token_path=".bambu_token.json")
    if not os.path.exists(".bambu_token.json"):
        if password:
            bambu.login(verify_code_prompt=prompt_for_verification_code)
        else:
            log.error(
                "No cached token found and no BAMBU_PASSWORD configured. "
                "If your account uses Google/SSO sign-in, manually extract a token "
                "as described in the README's 'Google/SSO accounts' section and "
                "save it to .bambu_token.json, then re-run."
            )
            return

    sheet = LocalSheetWriter(output_path)
    sheet.ensure_workbook()
    log.info(f"Writing filament log to {output_path}")

    state = StateStore("state.json")

    log.info(f"Starting poll loop, interval={poll_interval}s")
    while True:
        try:
            run_poll_cycle(bambu, sheet, state)
        except Exception:
            log.exception("Poll cycle failed, will retry next interval")
        time.sleep(poll_interval)


if __name__ == "__main__":
    main()
