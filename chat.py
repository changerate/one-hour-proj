import sys
import threading
import time
from pathlib import Path

import config
from auth import get_client
from sheet_repository import fetch_messages, open_sheet, send_message


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

    client = get_client(str(creds_path))
    ws = open_sheet(client, config.SPREADSHEET_ID, config.WORKSHEET_NAME)

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
