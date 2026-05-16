# Google Sheets Texting App

A minimal terminal chat that stores messages in a shared Google Sheet. Multiple users run `chat.py` with different usernames against the same spreadsheet.

## Prerequisites

- Python 3.10+
- A Google Cloud project with **Google Sheets API** and **Google Drive API** enabled
- A service account JSON key

## Google Cloud setup (one-time)

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create or select a project.
2. **APIs & Services → Library** — enable:
   - Google Sheets API
   - Google Drive API
3. **APIs & Services → Credentials → Create credentials → Service account**
   - Create the account, then open it → **Keys → Add key → JSON**
   - Save the file as `credentials/service_account.json`
4. Create a Google Spreadsheet with a worksheet tab named `messages`.
5. Row 1 must be the header:

   | id | timestamp | username | text |
   |----|-----------|----------|------|

6. **Share the spreadsheet** with the service account email (from the JSON file, field `client_email`) as **Editor**.
7. Copy the spreadsheet ID from the URL:
   `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit`

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set `SPREADSHEET_ID` to your sheet ID.

## Run

```bash
python chat.py
```

Enter a username, then type messages. New messages from others appear every few seconds (configurable via `POLL_SECONDS` in `.env`). Type `/quit` to exit.

## Project layout

```
auth.py              # Google service account client
config.py            # Environment variables
models.py            # Message dataclass
sheet_repository.py  # Append and fetch rows
chat.py              # Terminal UI (entry point)
credentials/         # service_account.json (not committed)
```

## Security notes

- Never commit `credentials/service_account.json` or `.env`.
- Usernames are not authenticated; anyone with the service account key can read or write the sheet.
- Google Sheets is polled, not pushed — expect a short delay before new messages appear.
