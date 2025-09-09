# test_mcp.py
import asyncio
import json
import os
from datetime import datetime, timedelta
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

SERVER_PATH = os.path.join(os.path.dirname(__file__), "server.py")

async def call(tool, args):
    params = StdioServerParameters(command="python", args=[SERVER_PATH], env=os.environ.copy())
    async with stdio_client(params) as (r, w):
        session = ClientSession(r, w)
        async with session:
            await session.initialize()
            res = await session.call_tool(name=tool, arguments=args)
            if getattr(res, "structuredContent", None) is not None:
                return res.structuredContent
            if getattr(res, "content", None):
                for c in res.content:
                    if hasattr(c, 'text') and c.text:
                        try:
                            return json.loads(c.text)
                        except Exception:
                            return {"raw_text": c.text}
            return {}

async def main():
    print("🧪 End-to-End MCP Test")
    # 1) doctor_lookup
    doctors_env = await call("doctor_lookup", {"condition": "fever", "visit_mode": "any"})
    doctors = doctors_env.get("result") if isinstance(doctors_env, dict) else doctors_env
    print("doctor_lookup →", doctors)
    if not isinstance(doctors, list) or not doctors:
        print("❌ doctor_lookup returned no doctors; check data/doctors.json")
        return
    doc = doctors[0]

    # 2) availability_tool - check next Monday (0 = Monday)
    monday = next_weekday(0)
    monday_iso = monday.isoformat()
    print(f"Checking availability for next clinic day (Monday): {monday_iso}")
    avail = await call("availability_tool", {"doctor_id": doc["doctor_id"], "date": monday_iso, "slot_minutes": 30})
    print("availability_tool →", avail)
    
    # Extract slots correctly from the nested 'result'
    avail_data = avail.get("result", {})
    slots = avail_data.get("slots", [])
    
    if not slots:
        print("⚠️ No free slots on the next clinic day; check calendar sharing permissions ('Make changes to events') or existing bookings.")
        return

    # Pick first slot and build start/end
    start_hm = slots[0]
    start = f"{monday_iso}T{start_hm}"
    end_dt = datetime.fromisoformat(start).replace(second=0, microsecond=0) + timedelta(minutes=30)
    end = end_dt.strftime("%Y-%m-%dT%H:%M")

    # 3) appointment_book_tool
    booking = await call("appointment_book_tool", {
        "doctor_id": doc["doctor_id"],
        "start": start,
        "end": end,
        "patient_name": "Test User",
        "patient_email": "abdulwaheed19026@gmail.com",
        "visit_mode": "online",
        "condition": "fever"
    })
    print("appointment_book_tool →", booking)

if __name__ == "__main__":
    from client import next_weekday # Import the helper
    asyncio.run(main()) 