# client.py
import os, json, asyncio
from openai import OpenAI
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from dotenv import load_dotenv
import re
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

# Load environment variables from .env
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SERVER_PATH = os.path.join(PROJECT_ROOT, "server.py")

SYSTEM_PROMPT = """You are Medbridge AI, a multilingual, concise triage & booking assistant.

MANDATORY DOCTOR DISPLAY FORMAT:
ALWAYS display doctors in this format: "Dr. [Name] - [Specialization]"
Examples:
- Dr. Eric - Ophthalmology
- Dr. Diego - Dermatology  
- Dr. Ali - General Medicine

Flow:
1) infer likely condition; 2) call doctor_lookup; 3) offer to check availability; 4) call availability_tool and show slots; 
5) when user picks a date, ALWAYS ask them to choose a specific time from slots; 
6) collect required fields (name, email) and optional (phone, age, sex);
7) BEFORE BOOKING, present a COMPLETE Review with ALL collected information in this exact format:

Here's a summary of your appointment details:
- Doctor: Dr. [Name] - [Specialization]
- Patient Name: [name]
- Patient Email: [email]
- Patient Phone: [phone if provided]
- Patient Age: [age if provided]
- Patient Sex: [sex if provided]
- Date: [full date with day name]
- Time: [HH:MM]
- Mode: [online/in-person]
- Fee: PKR [amount]
- Clinic: [location]

Then ask: "Please confirm to proceed with booking. Reply 'confirm' or 'yes' to book."
Only on explicit yes/confirm/book/go ahead call appointment_book_tool.

HARD REQUIREMENTS: 
- NEVER display doctor names without their specialization
- NEVER claim availability without availability_tool
- NEVER book without user confirmation and appointment_book_tool
STYLE: plain text; no asterisks; labeled lines; slot lists as '- HH:MM'; keep responses short.
Use the current date context provided in the system messages for all date calculations and references.
"""

FUNCTIONS = [
    {
        "name": "doctor_lookup",
        "description": "Find matching doctors for a condition and visit mode.",
        "parameters": {
            "type": "object",
            "properties": {
                "condition": {
                    "type": "string",
                    "enum": ["fever","headache","flu","eye_issue","skin_rash"]
                },
                "visit_mode": {
                    "type": "string",
                    "enum": ["online","inperson","any"],
                    "default": "any"
                }
            },
            "required": ["condition"]
        }
    },
    {
        "name": "availability_tool",
        "description": "List free appointment slots for a doctor on a date or date range.",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_id": {"type": "string"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "slot_minutes": {"type": "integer", "default": 30},
                "end_date": {"type": "string", "description": "Optional YYYY-MM-DD"}
            },
            "required": ["doctor_id", "date"]
        }
    },
    {
        "name": "appointment_book_tool",
        "description": "Book an appointment with the doctor.",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_id": {"type": "string"},
                "start": {"type": "string", "description": "YYYY-MM-DDTHH:MM (local)"},
                "end": {"type": "string", "description": "YYYY-MM-DDTHH:MM (local)"},
                "patient_name": {"type": "string"},
                "patient_email": {"type": "string"},
                "visit_mode": {"type": "string", "enum": ["online", "inperson", "any"]},
                "condition": {"type": "string"},
                "patient_phone": {"type": "string"},
                "patient_age": {"type": "integer"},
                "patient_sex": {"type": "string"}
            },
            "required": ["doctor_id", "start", "end", "patient_name", "patient_email"]
        }
    },
    {
        "name": "now_tool",
        "description": "Get current date/time in clinic timezone for phrase parsing.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "list_appointments_tool",
        "description": "List upcoming appointments by doctor and patient email.",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_id": {"type": "string"},
                "patient_email": {"type": "string"},
                "window_days": {"type": "integer", "default": 30}
            },
            "required": ["patient_email"]
        }
    },
    {
        "name": "cancel_appointment_tool",
        "description": "Cancel an appointment by event_id for the patient.",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_id": {"type": "string"},
                "event_id": {"type": "string"},
                "patient_email": {"type": "string"},
                "notify_attendees": {"type": "boolean", "default": True}
            },
            "required": ["doctor_id", "event_id", "patient_email"]
        }
    },
    {
        "name": "reschedule_tool",
        "description": "Reschedule an appointment to a new start/end for the patient.",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_id": {"type": "string"},
                "event_id": {"type": "string"},
                "new_start": {"type": "string", "description": "YYYY-MM-DDTHH:MM (local)"},
                "new_end": {"type": "string", "description": "YYYY-MM-DDTHH:MM (local)"},
                "patient_email": {"type": "string"}
            },
            "required": ["doctor_id", "event_id", "new_start", "new_end", "patient_email"]
        }
    }
]

CLINIC_TZ = os.getenv("CLINIC_TIMEZONE", "Asia/Karachi")

WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}


def contains_weekday_phrase(text: str) -> bool:
    t = (text or "").lower()
    if any(k in t for k in WEEKDAYS.keys()):
        return True
    if any(k in t for k in ["today", "tomorrow", "tmrw", "tmr", "tommorrow", "upcoming"]):
        return True
    return False


def next_weekday(target_idx: int, today: date | None = None) -> date:
    today = today or datetime.now(ZoneInfo(CLINIC_TZ)).date()
    delta = (target_idx - today.weekday()) % 7
    if delta == 0:
        delta = 7
    return today + timedelta(days=delta)


def to_iso_date_from_phrase(text: str, today: date | None = None) -> str | None:
    t = text.lower().strip()
    base_today = today or datetime.now(ZoneInfo(CLINIC_TZ)).date()
    if t in ("today",):
        return base_today.isoformat()
    if t in ("tomorrow",):
        return (base_today + timedelta(days=1)).isoformat()
    for key, idx in WEEKDAYS.items():
        if key in t:
            return next_weekday(idx, today=base_today).isoformat()
    # Already ISO?
    try:
        _ = datetime.fromisoformat(t)
        if len(t) == 10:
            return t
    except Exception:
        return None
    return None


def ensure_iso_date(input_value: str, fallback_text: str, today: date | None = None) -> str | None:
    # If already YYYY-MM-DD
    try:
        if len(input_value) == 10:
            datetime.fromisoformat(input_value)
            return input_value
    except Exception:
        pass
    # Try phrase using provided 'today'
    guess = to_iso_date_from_phrase(input_value, today=today)
    if guess:
        return guess
    # Try fallback text (e.g., user message)
    guess2 = to_iso_date_from_phrase(fallback_text, today=today)
    return guess2


class SessionState:
    def __init__(self) -> None:
        self.doctors_by_id: dict[str, dict] = {}
        self.doctors_by_name: dict[str, dict] = {}
        self.last_condition: str | None = None
        self.last_mode: str | None = None

    def update_from_doctors(self, doctors: list[dict]):
        self.doctors_by_id = {}
        self.doctors_by_name = {}
        for d in doctors:
            if not isinstance(d, dict):
                continue
            did = d.get("doctor_id")
            name = str(d.get("name", "")).lower().strip()
            if did:
                self.doctors_by_id[str(did)] = d
            if name:
                self.doctors_by_name[name] = d

    def resolve_doctor_id(self, args: dict, last_user_text: str | None = None) -> str | None:
        if "doctor_id" in args and args["doctor_id"] in self.doctors_by_id:
            return args["doctor_id"]
        name = (args.get("doctor_name") or args.get("name") or args.get("doctor") or "").lower().strip()
        if name and name in self.doctors_by_name:
            return self.doctors_by_name[name].get("doctor_id")
        if last_user_text:
            t = last_user_text.lower()
            # simple partial match on known doctor names
            for full_name, doc in self.doctors_by_name.items():
                parts = [p for p in full_name.split() if p]
                if any(p in t for p in parts):
                    return doc.get("doctor_id")
        if len(self.doctors_by_id) == 1:
            # Single result context
            return next(iter(self.doctors_by_id.keys()))
        return None


STATE = SessionState()

async def mcp_call(tool_name: str, args: dict):
    server_params = StdioServerParameters(
        command="python",
        args=[SERVER_PATH],
        env=os.environ.copy()
    )
    async with stdio_client(server_params) as (read_stream, write_stream):
        session = ClientSession(read_stream, write_stream)
        async with session:
            await session.initialize()
            result = await session.call_tool(name=tool_name, arguments=args)
            # Prefer structured content if present
            if getattr(result, "structuredContent", None) is not None:
                return result.structuredContent
            # Otherwise parse text content; if multiple items, aggregate JSON elements
            items = []
            if getattr(result, "content", None):
                for content_item in result.content:
                    if hasattr(content_item, 'text') and content_item.text:
                        try:
                            parsed = json.loads(content_item.text)
                            items.append(parsed)
                        except Exception:
                            items.append({"raw_text": content_item.text})
            if len(items) == 1:
                return items[0]
            if items:
                return items
            return {"ok": True}


def normalize_tool_args(fn: str, args: dict, last_user_text: str, last_assistant_text: str = "") -> dict:
    a = dict(args)
    if fn == "availability_tool":
        # Ensure doctor_id
        did = STATE.resolve_doctor_id(a, last_user_text=last_user_text)
        if did:
            a["doctor_id"] = did
        # Normalize date
        d = a.get("date")
        # Detect weekday phrase presence in user text
        has_weekday_phrase = any(k in last_user_text.lower() for k in WEEKDAYS.keys()) or any(w in last_user_text.lower() for w in ["today", "tomorrow"]) 
        if isinstance(d, str):
            # If user provided a weekday phrase, prefer recomputing from that phrase even if model provided ISO
            if has_weekday_phrase:
                guessed = ensure_iso_date("", last_user_text)
                if guessed:
                    a["date"] = guessed
                else:
                    fixed = ensure_iso_date(d, last_user_text)
                    if fixed:
                        a["date"] = fixed
            else:
                fixed = ensure_iso_date(d, last_user_text)
                if fixed:
                    a["date"] = fixed
        elif not d:
            # Try infer from user text first, then assistant hint (e.g., "Monday")
            guess = ensure_iso_date("", last_user_text)
            if not guess and last_assistant_text:
                guess = to_iso_date_from_phrase(last_assistant_text)
            if guess:
                a["date"] = guess
        # Default slot minutes
        a.setdefault("slot_minutes", 30)
    elif fn == "appointment_book_tool":
        did = STATE.resolve_doctor_id(a, last_user_text=last_user_text)
        if did:
            a["doctor_id"] = did
        # If only start given, compute end default 30m
        if a.get("start") and not a.get("end"):
            try:
                end_dt = datetime.fromisoformat(a["start"]).replace(second=0, microsecond=0) + timedelta(minutes=30)
                a["end"] = end_dt.strftime("%Y-%m-%dT%H:%M")
            except Exception:
                pass
        # Ensure minimal fields exist; model should fill name/email, but we won't inject fake data
    return a


def get_current_date_context() -> str:
    """Get current date context for the system prompt."""
    try:
        import pytz
        from datetime import datetime
        tz = pytz.timezone(CLINIC_TZ)
        now = datetime.now(tz)
        return f"Current date: {now.strftime('%A, %B %d, %Y')} ({now.strftime('%Y-%m-%d')})\nCurrent time: {now.strftime('%H:%M:%S')} ({now.tzinfo})\nToday is {now.strftime('%A')} (weekday index: {now.weekday()})"
    except Exception as e:
        return f"Current date: Unable to get date ({str(e)})"

def run_chat():
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY missing in .env")
    client = OpenAI(api_key=OPENAI_API_KEY)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Inject current date context
    date_context = get_current_date_context()
    messages.append({"role": "system", "content": date_context})
    
    print("Assistant ready. Type your message (Ctrl+C to exit).\n")

    # Prefetch doctors to enable name resolution before any lookup
    try:
        init_doctors = asyncio.run(mcp_call("list_doctors", {}))
        payload = init_doctors.get("result") if isinstance(init_doctors, dict) else init_doctors
        if isinstance(payload, list):
            STATE.update_from_doctors(payload)
    except Exception:
        pass

    last_assistant_textual = ""
    while True:
        try:
            user_msg = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!"); break
        if not user_msg:
            continue

        # Fetch authoritative 'today' from server
        today_override: date | None = None
        try:
            now_payload = asyncio.run(mcp_call("now_tool", {}))
            now_data = now_payload.get("result") if isinstance(now_payload, dict) else now_payload
            if isinstance(now_data, dict) and isinstance(now_data.get("date"), str):
                today_override = datetime.fromisoformat(now_data["date"]).date()
        except Exception:
            pass

        messages.append({"role": "user", "content": user_msg})

        nudge_attempts = 0
        while True:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=[{"type": "function", "function": f} for f in FUNCTIONS],
                tool_choice="auto",
                temperature=0.3,
            )
            msg = resp.choices[0].message

            # Handle tool calls iteratively until there are none
            if msg.tool_calls:
                messages.append({
                    "role": "assistant",
                    "tool_calls": [tc.model_dump() if hasattr(tc, 'model_dump') else {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                    } for tc in msg.tool_calls]
                })

                pending_sys_hint: str | None = None
                for tc in msg.tool_calls:
                    fn = tc.function.name
                    raw_args = json.loads(tc.function.arguments or "{}")
                    # Use server-provided 'today' for date phrase normalization
                    args = normalize_tool_args(fn, raw_args, user_msg, last_assistant_textual)
                    # Force override if the user used a weekday phrase
                    if fn == "availability_tool" and contains_weekday_phrase(user_msg):
                        if today_override:
                            forced = ensure_iso_date("", user_msg, today=today_override)
                        else:
                            forced = ensure_iso_date("", user_msg)
                        if forced:
                            args["date"] = forced
                    elif today_override:
                        if fn == "availability_tool":
                            if isinstance(args.get("date"), str):
                                fixed = ensure_iso_date(args["date"], user_msg, today=today_override)
                                if fixed:
                                    args["date"] = fixed
                            elif not args.get("date"):
                                guess = ensure_iso_date("", user_msg, today=today_override)
                                if guess:
                                    args["date"] = guess
                        elif fn == "appointment_book_tool":
                            # Booking expects full datetime; leave as provided
                            pass
                    # Capture state after doctor_lookup
                    if fn == "doctor_lookup":
                        STATE.last_condition = raw_args.get("condition")
                        STATE.last_mode = raw_args.get("visit_mode")
                    try:
                        result_json = asyncio.run(mcp_call(fn, args))
                    except Exception as e:
                        result_json = {"error": str(e)}
                    if fn == "doctor_lookup":
                        payload = result_json.get("result") if isinstance(result_json, dict) else result_json
                        if isinstance(payload, list):
                            STATE.update_from_doctors(payload)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": fn,
                        "content": json.dumps(result_json)
                    })
                    if fn == "availability_tool":
                        avail = result_json.get("result") if isinstance(result_json, dict) else result_json
                        if isinstance(avail, dict):
                            iso_date = avail.get("date") or ""
                            slots = avail.get("slots") or []
                            try:
                                dt = datetime.fromisoformat(iso_date)
                                human_date = dt.strftime('%a, %d %b %Y')
                            except Exception:
                                human_date = iso_date
                            sys_hint_lines = [
                                "Use the following tool-provided values exactly in your next message.",
                                f"Date: {human_date}",
                                "Slots:",
                            ]
                            sys_hint_lines += [f"- {s}" for s in slots]
                            sys_hint_lines.append("Do not change the year or re-compute the date. Ask the user to choose a slot.")
                            pending_sys_hint = "\n".join(sys_hint_lines)
                if pending_sys_hint:
                    messages.append({"role": "system", "content": pending_sys_hint})
                nudge_attempts = 0
                continue

            content_lower = (msg.content or "").lower()
            mentions_availability = any(k in content_lower for k in ["availability", "available", "slot", "schedule"])
            mentions_booking = any(k in content_lower for k in ["book", "booking", "reserve", "appointment"]) and "google" not in content_lower

            if nudge_attempts < 2 and (mentions_availability or mentions_booking):
                nudge_attempts += 1
                reminder = (
                    "Reminder: Per HARD REQUIREMENTS, you must call availability_tool before stating availability, "
                    "and call appointment_book_tool to book. If needed, ask for missing doctor_id or date/time."
                )
                messages.append({"role": "system", "content": reminder})
                continue

            print(f"\nAssistant: {msg.content}\n")
            last_assistant_textual = msg.content or ""
            messages.append({"role": "assistant", "content": msg.content or ""})
            break


if __name__ == "__main__":
    run_chat()
