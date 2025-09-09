import os, json, sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def main():
    load_dotenv()
    tz = os.getenv("CLINIC_TIMEZONE", "Asia/Karachi")
    sa_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not sa_path or not os.path.exists(sa_path):
        print(f"❌ Service account JSON not found. Set GOOGLE_SERVICE_ACCOUNT_FILE to an absolute path. Current: {sa_path}")
        sys.exit(1)

    # Resolve calendar id
    cal_id = os.getenv("DOCTOR_CALENDAR_ID")
    if not cal_id:
        data_path = os.path.join(os.path.dirname(__file__), "data", "doctors.json")
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                db = json.load(f)
            first = (db.get("doctors") or [])[0]
            cal_id = first.get("calendar_id") if first else None
        except Exception:
            cal_id = None
    if not cal_id:
        print("❌ No calendar_id found. Set DOCTOR_CALENDAR_ID or ensure data/doctors.json exists with doctors[].calendar_id")
        sys.exit(1)

    print(f"Using calendar_id: {cal_id}")
    scopes = ["https://www.googleapis.com/auth/calendar"]
    try:
        creds = Credentials.from_service_account_file(sa_path, scopes=scopes)
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    except Exception as e:
        print(f"❌ Failed to build Calendar client: {e}")
        sys.exit(1)

    # FreeBusy probe for today → +1 day
    now = datetime.now(ZoneInfo(tz))
    tmin = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tmax = tmin + timedelta(days=1)
    body = {
        "timeMin": tmin.astimezone(ZoneInfo("UTC")).isoformat(),
        "timeMax": tmax.astimezone(ZoneInfo("UTC")).isoformat(),
        "timeZone": tz,
        "items": [{"id": cal_id}],
    }

    try:
        fb = service.freebusy().query(body=body).execute()
        busy = fb.get("calendars", {}).get(cal_id, {}).get("busy", [])
        print(f"✅ FreeBusy OK. Busy blocks today: {len(busy)}")
    except HttpError as he:
        print(f"❌ FreeBusy HTTP error: {he}")
        if he.resp.status in (403, 404):
            print("Hint: Share the calendar with the service account and grant 'Make changes to events'.")
        sys.exit(2)
    except Exception as e:
        print(f"❌ FreeBusy error: {e}")
        sys.exit(2)

    # Optional: lightweight insert permissions probe (quickAdd to primary is not reliable). We skip destructive actions here.
    print("Diagnostics complete. Service account appears functional for FreeBusy.")


if __name__ == "__main__":
    main() 