import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "")
WORKSHEET_NAME = os.environ.get("WORKSHEET_NAME", "messages")
CREDENTIALS_PATH = os.environ.get(
    "CREDENTIALS_PATH",
    str(Path(__file__).parent / "credentials" / "service_account.json"),
)
POLL_SECONDS = float(os.environ.get("POLL_SECONDS", "2"))

COLUMNS = ("id", "timestamp", "username", "text")
