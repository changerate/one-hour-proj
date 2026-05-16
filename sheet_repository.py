import uuid
from datetime import datetime, timezone

import gspread
from gspread.exceptions import APIError

from debug_log import agent_log
from models import Message


def open_sheet(
    client: gspread.Client,
    spreadsheet_id: str,
    worksheet_name: str,
) -> gspread.Worksheet:
    # region agent log
    agent_log(
        "H4",
        "sheet_repository.py:open_sheet",
        "open_by_key_attempt",
        {
            "spreadsheet_id_len": len(spreadsheet_id),
            "worksheet_name": worksheet_name,
        },
    )
    # endregion
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
    except APIError as exc:
        # region agent log
        agent_log(
            "H1",
            "sheet_repository.py:open_sheet",
            "open_by_key_api_error",
            {
                "status_code": getattr(exc.response, "status_code", None),
                "error_text": str(exc)[:200],
            },
        )
        # endregion
        raise
    return spreadsheet.worksheet(worksheet_name)


def send_message(ws: gspread.Worksheet, username: str, text: str) -> Message:
    if "\n" in text or "\r" in text:
        raise ValueError("Multiline messages are not supported")
    if not text.strip():
        raise ValueError("Message cannot be empty")

    message = Message(
        id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        username=username.strip(),
        text=text.strip(),
    )
    ws.append_row(message.to_row(), value_input_option="USER_ENTERED")
    return message


def fetch_messages(
    ws: gspread.Worksheet,
    after_id: str | None = None,
) -> list[Message]:
    rows = ws.get_all_values()
    if len(rows) <= 1:
        return []

    messages: list[Message] = []
    for row in rows[1:]:
        if len(row) < 4 or not row[0].strip():
            continue
        try:
            messages.append(Message.from_row(row[:4]))
        except ValueError:
            continue

    messages.sort(key=lambda m: m.timestamp)

    if after_id is None:
        return messages

    seen = False
    result: list[Message] = []
    for msg in messages:
        if seen:
            result.append(msg)
        elif msg.id == after_id:
            seen = True
    return result
