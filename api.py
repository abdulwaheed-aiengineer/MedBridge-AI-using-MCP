from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os, json, asyncio, uuid, re
from typing import Optional, Dict, Any
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from openai import OpenAI
import server as mcp_tools
from fastapi.responses import RedirectResponse

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SERVER_PATH = os.path.join(PROJECT_ROOT, "server.py")

app = FastAPI(title="Medbridge AI API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Serve the static UI at /ui (serve index.html on /ui/)
app.mount("/ui", StaticFiles(directory=os.path.join(PROJECT_ROOT, "static"), html=True), name="ui")

# Redirect root to chat UI by default
@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/ui/chat.html")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """You are Medbridge AI, a bilingual triage & booking assistant supporting English and Roman Urdu only.
Flow:
1) If user asks about specific doctor by name, call doctor_lookup_by_name then doctor_weekly_availability;
2) If user has symptoms, infer likely condition and call doctor_lookup; 3) offer to check availability; 4) call availability_tool and show slots;
5) when user picks a date, ALWAYS ask them to choose a specific time from slots;
6) collect required fields (name, email) and optional (phone, age, sex);
7) BEFORE BOOKING, present a short Review with hyphen bullets (Doctor, Date, Time, Mode, Fee PKR, Clinic). Ask: Confirm to book? Only on explicit yes/confirm/book/go ahead call appointment_book_tool.
HARD REQUIREMENTS: never claim availability without availability_tool; never book without user confirmation and appointment_book_tool.
STYLE: plain text; no asterisks; labeled lines; slot lists as '- HH:MM'; keep responses short.
LANGUAGE: Only respond in English or Roman Urdu. Never use other languages like Spanish, French, etc.

CRITICAL AVAILABILITY FORMAT - THIS IS MANDATORY:
When showing doctor availability, you MUST format it EXACTLY like this:
Tuesday, September 09
- 11:00
- 11:30
- 12:00
- 12:30
- 16:00
- 16:30
- 17:00
- 17:30

Thursday, September 11
- 11:00
- 11:30
- 12:00
- 12:30

NEVER put all time slots on the same line with hyphens. Each time slot must be on its own line with a dash prefix. This is MANDATORY formatting.
"""

# --- Normalization helper ---
_ROMAN_URDU_MAP = {
    "bukhar": "fever",
    "sar dard": "headache",
    "sirdard": "headache",
    "headache": "headache",
    "migraine": "headache",
    "zukam": "flu",
    "jukam": "flu",
    "khansi": "cough",
    "ankh": "eye_issue",
    "aankh": "eye_issue",
    "ankhon": "eye_issue",
    "eye issue": "eye_issue",
    "eye problem": "eye_issue",
    "derma": "skin_rash",
    "dermatology": "skin_rash",
    "dermatologist": "skin_rash",
    "skin": "skin_rash",
    "skin issue": "skin_rash",
    "skin problem": "skin_rash",
    "skiin": "skin_rash",
    "kharish": "skin_rash",
    "khaarish": "skin_rash",
    "khujli": "skin_rash",
    "itch": "skin_rash",
    "itching": "skin_rash",
    "acne": "skin_rash",
    "pimple": "skin_rash",
    "rashes": "skin_rash",
    "jild": "skin_rash",
    "rash": "skin_rash",
    "daane": "skin_rash",
}

def _normalization_hint(text: str) -> str | None:
    t = (text or "").lower()
    hits = []
    for k, v in _ROMAN_URDU_MAP.items():
        if k in t:
            hits.append(f"{k}→{v}")
    if hits:
        return "Normalization hint: interpret roman-Urdu tokens as → " + ", ".join(sorted(set(hits)))
    return None

def _detect_language(text: str) -> str:
    """
    Detect if text is in Roman Urdu or English.
    Returns 'urdu' for Roman Urdu, 'english' for English.
    """
    # Check for Roman Urdu patterns
    roman_urdu_indicators = [
        "bukhar", "sar dard", "sirdard", "zukam", "jukam", "khansi", 
        "ankh", "aankh", "ankhon", "derma", "kharish", "khaarish", 
        "khujli", "jild", "daane", "hai", "hain", "ka", "ki", "ke", 
        "mein", "ko", "se", "par", "tak", "bhi", "ya", "aur"
    ]
    
    text_lower = text.lower()
    urdu_count = sum(1 for indicator in roman_urdu_indicators if indicator in text_lower)
    
    # If we find Roman Urdu indicators, classify as Urdu
    if urdu_count > 0:
        return "urdu"
    
    # Default to English
    return "english"

def _translate_to_english(text: str) -> Dict[str, str]:
    """
    Translate Roman Urdu to English, or keep English as is.
    Only supports English and Roman Urdu - other languages are not supported.
    """
    detected_lang = _detect_language(text)
    
    if detected_lang == "english":
        return {"lang": "english", "english": text}
    
    # For Roman Urdu, try to translate to English
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.0,
            messages=[
                {"role": "system", "content": "Translate Roman Urdu text to English for medical scheduling context. Only translate if the text contains Roman Urdu words. If it's already English, return as is. Reply strictly as JSON: {\"lang\": \"urdu\" or \"english\", \"english\": \"<english_translation>\"}. Do not add any extra text."},
                {"role": "user", "content": text},
            ],
        )
        raw = resp.choices[0].message.content or ""
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("english"):
            return {"lang": str(data.get("lang") or "urdu"), "english": str(data.get("english"))}
    except Exception:
        pass
    
    # Fallback: treat as English
    return {"lang": "english", "english": text}

def _classify_intent_condition(text: str) -> str | None:
    """
    Use the LLM to map user text to one of known conditions:
    {fever, headache, flu, eye_issue, skin_rash}.
    Returns the condition string or None.
    """
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        prompt = (
            "Classify the user's health concern into one of: fever, headache, flu, eye_issue, skin_rash. "
            "If none applies, return none. Reply strictly as JSON: {\"condition\": \"<one_of_above_or_none>\"}."
        )
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.0,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
        )
        raw = resp.choices[0].message.content or ""
        data = json.loads(raw)
        cond = (data or {}).get("condition")
        if isinstance(cond, str):
            cond = cond.strip().lower()
            if cond in {"fever", "headache", "flu", "eye_issue", "skin_rash"}:
                return cond
    except Exception:
        pass
    return None


def _detect_doctor_name(text: str) -> str | None:
    """
    Detect if user is asking about a specific doctor by name.
    Returns doctor name if found, None otherwise.
    """
    # Check for known doctor names from the database
    known_doctors = ["Dr. Eric", "Dr. Diego", "Dr. Ali", "Eric", "Diego", "Ali"]
    
    text_lower = text.lower()
    for doctor in known_doctors:
        if doctor.lower() in text_lower:
            # Return the proper name format
            if doctor.startswith("Dr."):
                return doctor
            else:
                return f"Dr. {doctor}"
    
    # Check for general doctor patterns
    import re
    patterns = [
        r"dr\.?\s+(\w+)",
        r"doctor\s+(\w+)",
        r"(\w+)\s+doctor"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            name = match.group(1).title()
            return f"Dr. {name}"
    
    return None

def _build_session_hint(state: Dict[str, Any]) -> str:
    parts: list[str] = []
    cond = state.get("last_condition")
    if isinstance(cond, str) and cond:
        parts.append(f"condition={cond}")
    doctors = state.get("last_doctor_options") or []
    if isinstance(doctors, list) and doctors:
        try:
            names = ", ".join([f"{d.get('name')}({d.get('doctor_id')})" for d in doctors if isinstance(d, dict)])
            parts.append(f"doctor_options=[{names}]")
        except Exception:
            pass
    avail = state.get("last_availability") or {}
    if isinstance(avail, dict) and avail.get("doctor_name") and avail.get("date"):
        parts.append(f"last_availability={avail.get('doctor_name')} on {avail.get('date')}")
    lang = state.get("lang")
    if isinstance(lang, str) and lang:
        parts.append(f"user_lang={lang}")
    summary = "; ".join(parts) or "none"
    return (
        "Session memory: " + summary + ". "
        "When helpful, begin your reply with a one-line recap of the plan before proceeding."
    )

def _force_proper_formatting(content: str) -> str:
    """
    Force proper formatting for availability information regardless of AI output.
    This is a post-processing step to ensure clean formatting.
    """
    if not content:
        return content
    
    # Pattern to match the messy format: "**Tuesday, September 09** - 11:00 - 11:30 - 12:00..."
    messy_pattern = r'\*\*([^*]+?)\*\*\s*-\s*([^*-]+?)(?=\*\*|$)'
    
    def replace_messy_format(match):
        date_part = match.group(1).strip()
        time_part = match.group(2).strip()
        
        # Extract individual time slots
        time_slots = re.findall(r'\d{1,2}:\d{2}', time_part)
        
        # Build properly formatted result
        result = f"{date_part}\n"
        for time_slot in time_slots:
            result += f"- {time_slot}\n"
        
        return result
    
    # Apply the formatting fix
    formatted_content = re.sub(messy_pattern, replace_messy_format, content)
    
    # Also handle cases where there might be multiple dates in sequence
    # Look for patterns like "Date: Tuesday, September 09 - 11:00 - 11:30..."
    date_pattern = r'Date:\s*([^-\n]+?)\s*-\s*([^D]+?)(?=Date:|$)'
    
    def replace_date_format(match):
        date_part = match.group(1).strip()
        time_part = match.group(2).strip()
        
        # Extract individual time slots
        time_slots = re.findall(r'\d{1,2}:\d{2}', time_part)
        
        # Build properly formatted result
        result = f"{date_part}\n"
        for time_slot in time_slots:
            result += f"- {time_slot}\n"
        
        return result
    
    formatted_content = re.sub(date_pattern, replace_date_format, formatted_content)
    
    return formatted_content

FUNCTIONS = [
    {
        "name": "doctor_lookup",
        "description": "Find matching doctors for a condition and visit mode.",
        "parameters": {
            "type": "object",
            "properties": {
                "condition": {"type": "string"},
                "visit_mode": {"type": "string", "enum": ["online", "inperson", "any"], "default": "any"}
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
                "date": {"type": "string"},
                "slot_minutes": {"type": "integer", "default": 30},
                "end_date": {"type": "string"}
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
                "start": {"type": "string"},
                "end": {"type": "string"},
                "patient_name": {"type": "string"},
                "patient_email": {"type": "string"},
                "visit_mode": {"type": "string"},
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
                "new_start": {"type": "string"},
                "new_end": {"type": "string"},
                "patient_email": {"type": "string"}
            },
            "required": ["doctor_id", "event_id", "new_start", "new_end", "patient_email"]
        }
    },
    {
        "name": "doctor_lookup_by_name",
        "description": "Find a doctor by name and return their details.",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_name": {"type": "string"}
            },
            "required": ["doctor_name"]
        }
    },
    {
        "name": "doctor_weekly_availability",
        "description": "Get doctor availability for the next N days based on routine schedule + Google Calendar.",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_name": {"type": "string"},
                "days": {"type": "integer", "default": 7},
                "slot_minutes": {"type": "integer", "default": 30}
            },
            "required": ["doctor_name"]
        }
    }
]

SESSIONS: Dict[str, Dict[str, Any]] = {}

# In-process tool map
TOOL_MAP = {
    "doctor_lookup": mcp_tools.doctor_lookup,
    "availability_tool": mcp_tools.availability_tool,
    "appointment_book_tool": mcp_tools.appointment_book_tool,
    "list_appointments_tool": mcp_tools.list_appointments_tool,
    "cancel_appointment_tool": mcp_tools.cancel_appointment_tool,
    "reschedule_tool": mcp_tools.reschedule_tool,
    "doctor_lookup_by_name": mcp_tools.doctor_lookup_by_name,
    "doctor_weekly_availability": mcp_tools.doctor_weekly_availability,
    "now_tool": mcp_tools.now_tool,
}

async def mcp_call(tool_name: str, args: dict):
    func = TOOL_MAP.get(tool_name)
    if func:
        try:
            # Run the sync tool in a thread to avoid blocking the event loop
            return await asyncio.to_thread(func, **args)
        except Exception as e:
            # Fall back to stdio approach if direct call fails for any reason
            pass
    # Fallback: spawn MCP server via stdio
    params = StdioServerParameters(command="python", args=[SERVER_PATH], env=os.environ.copy())
    async with stdio_client(params) as (r, w):
        session = ClientSession(r, w)
        async with session:
            await session.initialize()
            res = await session.call_tool(name=tool_name, arguments=args)
            if getattr(res, "structuredContent", None) is not None:
                payload = res.structuredContent
            else:
                items = []
                if getattr(res, "content", None):
                    for c in res.content:
                        if getattr(c, "text", None):
                            try:
                                items.append(json.loads(c.text))
                            except Exception:
                                items.append({"raw_text": c.text})
                payload = items[0] if len(items) == 1 else (items or {"ok": True})
            return payload

class ChatIn(BaseModel):
    session_id: Optional[str] = None
    user: str
    language: Optional[str] = "en"

@app.post("/chat")
async def chat(body: ChatIn):
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY missing")
    
    session_id = body.session_id or str(uuid.uuid4())
    session = SESSIONS.setdefault(session_id, {"messages": [{"role": "system", "content": SYSTEM_PROMPT}]})
    messages = session["messages"]

    # Inject normalization hint if roman Urdu tokens detected
    hint = _normalization_hint(body.user)
    if hint:
        messages.append({"role": "system", "content": hint})

    # Session memory hint - maintain conversation context
    session_hint = _build_session_hint(session)
    messages.append({"role": "system", "content": session_hint})
    
    # Translate user message to English and inject hint
    translated_user_message = _translate_to_english(body.user)
    messages.append({"role": "system", "content": f"User message in {translated_user_message['lang']}: {body.user}\nEnglish translation: {translated_user_message['english']}"})
    # Intent classification hint
    _intent = _classify_intent_condition(translated_user_message['english'])
    if _intent:
        messages.append({"role": "system", "content": f"Intent condition: {_intent}. If symptoms are present, call doctor_lookup with condition='{_intent}'."})
        # Update session with detected condition
        session["last_condition"] = _intent
    # Update session with language
    session["lang"] = translated_user_message['lang']
    
    # Doctor name detection
    detected_doctor = _detect_doctor_name(translated_user_message['english'])
    if detected_doctor:
        messages.append({"role": "system", "content": f"User asking about specific doctor: {detected_doctor}. Call doctor_lookup_by_name with doctor_name='{detected_doctor}' to find the doctor, then doctor_weekly_availability to show their schedule for next 7 days."})
        session["last_doctor_query"] = detected_doctor
    
    
    # Reply language hint - RESTRICTED TO ENGLISH AND ROMAN URDU ONLY
    if translated_user_message['lang'] == 'urdu':
        messages.append({"role": "system", "content": "Respond in Roman Urdu (English script with Urdu words). Keep tool arguments in English."})
    else:
        messages.append({"role": "system", "content": "Respond in English. Keep tool arguments in English."})
    
    # Strict tool usage
    messages.append({"role": "system", "content": "For any current date/time or day-of-week question, call now_tool and answer from it. For any slots/dates/times, call availability_tool and only present what it returns. If the user challenges availability, re-check availability_tool for the mentioned date and correct yourself."})
    # Fallback rule hint
    messages.append({"role": "system", "content": "If doctor_lookup returns empty, suggest a General Physician (Dr. Ali) instead of saying no doctors available."})

    messages.append({"role": "user", "content": body.user})

    client = OpenAI(api_key=OPENAI_API_KEY)

    # Tool loop with retry logic
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                tools=[{"type": "function", "function": f} for f in FUNCTIONS],
                tool_choice="auto",
                temperature=0.3,
            )
            msg = resp.choices[0].message
            if msg.tool_calls:
                messages.append({
                    "role": "assistant",
                    "tool_calls": [tc.model_dump() if hasattr(tc, 'model_dump') else {
                        "id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                    } for tc in msg.tool_calls]
                })
                for tc in msg.tool_calls:
                    fn = tc.function.name
                    try:
                        raw_args = json.loads(tc.function.arguments or "{}")
                    except Exception:
                        raw_args = {}
                    try:
                        result_json = await mcp_call(fn, raw_args)
                        # Update session state based on tool results
                        if fn == "doctor_lookup" and isinstance(result_json, dict):
                            doctors = result_json.get("result", [])
                            if isinstance(doctors, list):
                                session["last_doctor_options"] = doctors
                        elif fn == "availability_tool" and isinstance(result_json, dict):
                            avail_data = result_json.get("result", {})
                            if isinstance(avail_data, dict):
                                session["last_availability"] = {
                                    "doctor_name": avail_data.get("doctor_name"),
                                    "date": avail_data.get("date"),
                                    "slots": avail_data.get("slots", [])
                                }
                    except Exception as e:
                        result_json = {"error": str(e)}
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": fn,
                        "content": json.dumps(result_json)
                    })
                continue
            # final
            content = msg.content or ""
            # Apply forced formatting fix
            content = _force_proper_formatting(content)
            messages.append({"role": "assistant", "content": content})
            return {"session_id": session_id, "assistant": content}
            
        except Exception as e:
            retry_count += 1
            if retry_count >= max_retries:
                raise HTTPException(status_code=500, detail=f"Failed after {max_retries} retries: {str(e)}")
            # Wait before retry with exponential backoff
            await asyncio.sleep(2 ** retry_count)

@app.post("/chat/stream")
async def chat_stream(body: ChatIn):
    """Streaming chat endpoint for better UX"""
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY missing")
    
    session_id = body.session_id or str(uuid.uuid4())
    session = SESSIONS.setdefault(session_id, {"messages": [{"role": "system", "content": SYSTEM_PROMPT}]})
    messages = session["messages"]

    # Inject normalization hint if roman Urdu tokens detected
    hint = _normalization_hint(body.user)
    if hint:
        messages.append({"role": "system", "content": hint})

    # Session memory hint - maintain conversation context
    session_hint = _build_session_hint(session)
    messages.append({"role": "system", "content": session_hint})
    
    # Translate user message to English and inject hint
    translated_user_message = _translate_to_english(body.user)
    messages.append({"role": "system", "content": f"User message in {translated_user_message['lang']}: {body.user}\nEnglish translation: {translated_user_message['english']}"})
    # Intent classification hint
    _intent = _classify_intent_condition(translated_user_message['english'])
    if _intent:
        messages.append({"role": "system", "content": f"Intent condition: {_intent}. If symptoms are present, call doctor_lookup with condition='{_intent}'."})
        # Update session with detected condition
        session["last_condition"] = _intent
    # Update session with language
    session["lang"] = translated_user_message['lang']
    
    # Doctor name detection
    detected_doctor = _detect_doctor_name(translated_user_message['english'])
    if detected_doctor:
        messages.append({"role": "system", "content": f"User asking about specific doctor: {detected_doctor}. Call doctor_lookup_by_name with doctor_name='{detected_doctor}' to find the doctor, then doctor_weekly_availability to show their schedule for next 7 days."})
        session["last_doctor_query"] = detected_doctor
    
    
    # Reply language hint - RESTRICTED TO ENGLISH AND ROMAN URDU ONLY
    if translated_user_message['lang'] == 'urdu':
        messages.append({"role": "system", "content": "Respond in Roman Urdu (English script with Urdu words). Keep tool arguments in English."})
    else:
        messages.append({"role": "system", "content": "Respond in English. Keep tool arguments in English."})
    
    # Strict tool usage
    messages.append({"role": "system", "content": "For any current date/time or day-of-week question, call now_tool and answer from it. For any slots/dates/times, call availability_tool and only present what it returns. If the user challenges availability, re-check availability_tool for the mentioned date and correct yourself."})
    # Fallback rule hint
    messages.append({"role": "system", "content": "If doctor_lookup returns empty, suggest a General Physician (Dr. Ali) instead of saying no doctors available."})

    messages.append({"role": "user", "content": body.user})

    client = OpenAI(api_key=OPENAI_API_KEY)

    async def generate():
        try:
            # First, try to get a complete response without streaming to handle tool calls
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    resp = client.chat.completions.create(
                        model=OPENAI_MODEL,
                        messages=messages,
                        tools=[{"type": "function", "function": f} for f in FUNCTIONS],
                        tool_choice="auto",
                        temperature=0.3,
                    )
                    msg = resp.choices[0].message
                    
                    if msg.tool_calls:
                        # Handle tool calls
                        messages.append({
                            "role": "assistant",
                            "tool_calls": [tc.model_dump() if hasattr(tc, 'model_dump') else {
                                "id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                            } for tc in msg.tool_calls]
                        })
                        
                        for tc in msg.tool_calls:
                            fn = tc.function.name
                            try:
                                raw_args = json.loads(tc.function.arguments or "{}")
                            except Exception:
                                raw_args = {}
                            try:
                                result_json = await mcp_call(fn, raw_args)
                                # Update session state based on tool results
                                if fn == "doctor_lookup" and isinstance(result_json, dict):
                                    doctors = result_json.get("result", [])
                                    if isinstance(doctors, list):
                                        session["last_doctor_options"] = doctors
                                elif fn == "availability_tool" and isinstance(result_json, dict):
                                    avail_data = result_json.get("result", {})
                                    if isinstance(avail_data, dict):
                                        session["last_availability"] = {
                                            "doctor_name": avail_data.get("doctor_name"),
                                            "date": avail_data.get("date"),
                                            "slots": avail_data.get("slots", [])
                                        }
                            except Exception as e:
                                result_json = {"error": str(e)}
                            # Track availability date for ISO echoing
                            try:
                                payload = result_json.get("result") if isinstance(result_json, dict) else result_json
                                if fn == "availability_tool" and isinstance(payload, dict):
                                    last_avail_date = payload.get("date")
                            except Exception:
                                pass
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "name": fn,
                                "content": json.dumps(result_json)
                            })
                        
                        # Continue the loop to get the final response
                        continue
                    
                    # Final response without tool calls
                    content = msg.content or ""
                    # Apply forced formatting fix
                    content = _force_proper_formatting(content)
                    messages.append({"role": "assistant", "content": content})
                    
                    # Stream the final content
                    words = content.split()
                    for i, word in enumerate(words):
                        yield f"data: {json.dumps({'content': word + ' ', 'session_id': session_id})}\n\n"
                        await asyncio.sleep(0.05)  # Small delay for streaming effect
                    
                    yield f"data: {json.dumps({'done': True, 'session_id': session_id})}\n\n"
                    return
                    
                except Exception as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        raise e
                    await asyncio.sleep(2 ** retry_count)
            
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/plain")

class DoctorLookupIn(BaseModel):
    condition: str
    visit_mode: Optional[str] = "any"

class AvailabilityIn(BaseModel):
    doctor_id: str
    date: str
    slot_minutes: Optional[int] = 30
    end_date: Optional[str] = None

class BookIn(BaseModel):
    doctor_id: str
    start: str
    end: str
    patient_name: str
    patient_email: str
    visit_mode: Optional[str] = None
    condition: Optional[str] = None
    patient_phone: Optional[str] = None
    patient_age: Optional[int] = None
    patient_sex: Optional[str] = None
    send_invitations: Optional[bool] = False
    create_meet: Optional[bool] = False

class ListApptsIn(BaseModel):
    patient_email: str
    doctor_id: Optional[str] = None
    window_days: Optional[int] = 30

class CancelIn(BaseModel):
    doctor_id: str
    event_id: str
    patient_email: str
    notify_attendees: Optional[bool] = True

class RescheduleIn(BaseModel):
    new_start: str
    new_end: str
    patient_email: str

class RehydrateIn(BaseModel):
    session_id: str
    messages: list[dict]

@app.get("/health")
async def health():
    return {"ok": True}

@app.post("/doctor-lookup")
async def doctor_lookup(body: DoctorLookupIn):
    return await mcp_call("doctor_lookup", body.model_dump())

@app.post("/availability")
async def availability(body: AvailabilityIn):
    return await mcp_call("availability_tool", body.model_dump())

@app.post("/book")
async def book(body: BookIn):
    return await mcp_call("appointment_book_tool", body.model_dump())

@app.post("/appointments")
async def list_appts(body: ListApptsIn):
    return await mcp_call("list_appointments_tool", body.model_dump())

@app.post("/cancel")
async def cancel(body: CancelIn):
    return await mcp_call("cancel_appointment_tool", body.model_dump())

@app.post("/reschedule")
async def reschedule(body: RescheduleIn):
    return await mcp_call("reschedule_tool", body.model_dump())

@app.post("/rehydrate")
async def rehydrate(body: RehydrateIn):
    # Rebuild session messages with system prompt and provided history
    session = SESSIONS.setdefault(body.session_id, {"messages": [{"role": "system", "content": SYSTEM_PROMPT}]})
    # Filter only valid roles/content
    cleaned = []
    for m in body.messages:
        try:
            role = m.get("role")
            content = m.get("content")
            if role in {"user", "assistant", "system"} and isinstance(content, str) and content.strip():
                cleaned.append({"role": role, "content": content})
        except Exception:
            continue
    # Keep only last 50 messages to bound memory
    session["messages"] = session["messages"][:1] + cleaned[-50:]
    return {"ok": True, "session_id": body.session_id, "count": len(cleaned)}


def main():
    import uvicorn, webbrowser, threading, time
    port = int(os.getenv("PORT", "8000"))
    # Default to chat page
    url = os.getenv("APP_OPEN_URL", f"http://localhost:{port}/ui/chat.html")
    if os.getenv("OPEN_BROWSER", "1") != "0":
        def _open():
            time.sleep(1.5)
            try:
                webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True).start()
    uvicorn.run("api:app", host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
