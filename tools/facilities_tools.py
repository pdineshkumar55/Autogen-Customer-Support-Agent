from data.mock_db import MEETING_ROOMS, ROOM_BOOKINGS
from tools.common import employee_error


def book_meeting_room(employee_id: str, room: str, date: str,
                      start_time: str, duration_minutes: int) -> dict:
    """Book a meeting room. room: Everest, Nilgiri or Kanchenjunga.
    date YYYY-MM-DD, start_time HH:MM (24h)."""
    if err := employee_error(employee_id):
        return err
    if room not in MEETING_ROOMS:
        return {"error": f"Unknown room. Choose from {list(MEETING_ROOMS)}."}
    clash = any(b["room"] == room and b["date"] == date and b["start_time"] == start_time
                for b in ROOM_BOOKINGS)
    if clash:
        return {"error": f"{room} is already booked at {start_time} on {date}."}
    booking = {"room": room, "date": date, "start_time": start_time,
               "duration_minutes": duration_minutes, "employee_id": employee_id}
    ROOM_BOOKINGS.append(booking)
    return {"status": "booked", "capacity": MEETING_ROOMS[room], **booking}


def request_access_card(employee_id: str, reason: str) -> dict:
    """Request a new or replacement ID/access card (lost, damaged or new joiner)."""
    if err := employee_error(employee_id):
        return err
    return {"status": "requested", "pickup": "Security desk, ground floor, next working day.",
            "note": "A temporary visitor pass can be issued today."}