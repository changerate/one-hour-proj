import json
import sys
import threading
import time
from pathlib import Path

import config
from auth import get_client
from debug_log import agent_log
from sheet_repository import fetch_messages, open_sheet, send_message


def _permission_diagnostics(spreadsheet_id: str, credentials_path: str) -> dict:
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
        drive = build("drive", "v3", credentials=creds, cache_discovery=False)
        try:
            drive.files().get(fileId=spreadsheet_id, fields="id,name").execute()
            return {"drive_status": 200, "sheets_status": 403}
        except HttpError as err:
            return {
                "drive_status": err.resp.status,
                "drive_error": str(err)[:200],
            }
    except Exception as err:
        return {"diagnostics_error": type(err).__name__}


def _format_time(iso_timestamp: str) -> str:
    if "T" in iso_timestamp:
        return iso_timestamp.split("T")[1].replace("Z", "")[:5]
    return iso_timestamp[:5]


def _print_message(msg, username: str) -> None:
    prefix = "You" if msg.username == username else msg.username
    print(f"[{_format_time(msg.timestamp)}] {prefix}: {msg.text}")


def _poll_loop(ws, username: str, state: dict, stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            new_messages = fetch_messages(ws, after_id=state.get("last_seen_id"))
            for msg in new_messages:
                _print_message(msg, username)
                state["last_seen_id"] = msg.id
        except Exception as exc:
            print(f"Poll error: {exc}", file=sys.stderr)
        stop.wait(config.POLL_SECONDS)


def main() -> None:
    if not config.SPREADSHEET_ID:
        print("Set SPREADSHEET_ID in .env (see .env.example)", file=sys.stderr)
        sys.exit(1)

    creds_path = Path(config.CREDENTIALS_PATH)
    if not creds_path.is_file():
        print(f"Credentials not found: {creds_path}", file=sys.stderr)
        print("See README.md for Google Cloud setup.", file=sys.stderr)
        sys.exit(1)

    username = input("Username: ").strip()
    if not username:
        print("Username is required.", file=sys.stderr)
        sys.exit(1)

    creds_meta: dict = {}
    try:
        with creds_path.open(encoding="utf-8") as f:
            sa = json.load(f)
        creds_meta = {
            "client_email": sa.get("client_email", ""),
            "project_id": sa.get("project_id", ""),
            "credentials_basename": creds_path.name,
        }
    except Exception as exc:
        creds_meta = {"credentials_parse_error": type(exc).__name__}

    # region agent log
    agent_log(
        "H2",
        "chat.py:main",
        "config_loaded",
        {
            "spreadsheet_id_len": len(config.SPREADSHEET_ID),
            "spreadsheet_id_prefix": config.SPREADSHEET_ID[:4],
            "spreadsheet_id_suffix": config.SPREADSHEET_ID[-4:],
            "worksheet_name": config.WORKSHEET_NAME,
            "credentials_path": str(creds_path),
            "credentials_exists": creds_path.is_file(),
            **creds_meta,
        },
    )
    # endregion

    client = get_client(str(creds_path))
    try:
        ws = open_sheet(client, config.SPREADSHEET_ID, config.WORKSHEET_NAME)
    except PermissionError as exc:
        diag = _permission_diagnostics(config.SPREADSHEET_ID, str(creds_path))
        # region agent log
        agent_log(
            "H1",
            "chat.py:main",
            "open_sheet_permission_denied",
            {
                "error": type(exc).__name__,
                "share_with_email": creds_meta.get("client_email", ""),
                **creds_meta,
                **diag,
            },
        )
        # endregion
        email = creds_meta.get("client_email", "service account email from JSON")
        sid = config.SPREADSHEET_ID
        print(
            f"Permission denied. The service account still cannot access this spreadsheet.\n"
            f"  Spreadsheet ID in .env: {sid[:8]}...{sid[-4:]}\n"
            f"  Share THIS exact file (URL ID must match) with:\n"
            f"    {email}\n"
            f"  Role: Editor\n",
            file=sys.stderr,
        )
        if diag.get("drive_status") == 404:
            print(
                "  Diagnosis: Drive API returns 'file not found' for the service account.\n"
                "  Usually the sheet was not shared with that email, or .env points at a\n"
                "  different spreadsheet than the one you shared.\n",
                file=sys.stderr,
            )
        sys.exit(1)
    except Exception as exc:
        # region agent log
        agent_log(
            "H3",
            "chat.py:main",
            "open_sheet_failed",
            {
                "error": type(exc).__name__,
                "detail": str(exc)[:200],
                **creds_meta,
            },
        )
        # endregion
        raise

    # region agent log
    agent_log(
        "H5",
        "chat.py:main",
        "open_sheet_success",
        {"worksheet_title": ws.title, "spreadsheet_title": ws.spreadsheet.title},
    )
    # endregion

    state: dict = {"last_seen_id": None}
    stop = threading.Event()
    poller = threading.Thread(
        target=_poll_loop,
        args=(ws, username, state, stop),
        daemon=True,
    )
    poller.start()

    print(f"Connected. Type a message and press Enter (/quit to exit).")

    try:
        while True:
            try:
                text = input(f"{username}> ")
            except EOFError:
                break

            if text.strip().lower() in ("/quit", "/exit"):
                break
            if not text.strip():
                continue

            try:
                msg = send_message(ws, username, text)
                state["last_seen_id"] = msg.id
                _print_message(msg, username)
            except ValueError as exc:
                print(f"Error: {exc}", file=sys.stderr)
            except Exception as exc:
                print(f"Send error: {exc}", file=sys.stderr)
    finally:
        stop.set()
        poller.join(timeout=config.POLL_SECONDS + 1)
        print("Goodbye.")


if __name__ == "__main__":
    main()
