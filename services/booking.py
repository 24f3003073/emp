"""Business rules for slots, bookings and evaluation marks."""
from datetime import date, datetime

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Booking, Notification, Slot
from services import cache
from utils import ApiError, as_int, parse_date, parse_time


def notify(user_id, message, kind="info", payload=None):
    db.session.add(Notification(user_id=user_id, message=message, kind=kind, payload=payload))


# ---------- slots ----------
def fill_slot(slot, d):
    """Apply and validate slot fields (date, times, capacity, link)."""
    if "date" in d:
        slot.date = parse_date(d["date"])
    if "start_time" in d:
        slot.start_time = parse_time(d["start_time"])
    if "end_time" in d:
        slot.end_time = parse_time(d["end_time"])
    if not (slot.date and slot.start_time and slot.end_time):
        raise ApiError("date, start_time and end_time are required")
    if slot.start_time >= slot.end_time:
        raise ApiError("End time must be after start time")

    booked = (slot.capacity - slot.available_seats) if slot.id else 0
    if "capacity" in d:
        cap = as_int(d["capacity"], "Capacity", 1)
        if cap < booked:
            raise ApiError(f"Capacity cannot be lower than the {booked} students already booked")
        slot.capacity = cap
    elif slot.capacity is None:
        slot.capacity = 1
    slot.available_seats = slot.capacity - booked

    if "meeting_link" in d:
        slot.meeting_link = (d["meeting_link"] or "").strip() or None
    if slot.status in ("Available", "Full"):
        slot.status = "Full" if slot.available_seats == 0 else "Available"

    clash = Slot.query.filter(
        Slot.examiner_id == slot.examiner_id, Slot.date == slot.date,
        Slot.status != "Cancelled", Slot.id != slot.id,
        Slot.start_time < slot.end_time, Slot.end_time > slot.start_time).first()
    if clash:
        raise ApiError("This examiner already has a slot overlapping that time")


# ---------- bookings ----------
def book_slot(student, slot):
    exam = slot.exam
    if not exam.booking_active:
        raise ApiError("Slot booking is not open for this examination right now")
    if slot.status in ("Cancelled", "Completed"):
        raise ApiError("This slot is not available")
    if Booking.query.filter_by(student_id=student.id, exam_id=exam.id, active_key=1).first():
        raise ApiError("You already have a booking for this examination", 409)

    # Atomic seat decrement: succeeds only while a seat is left (prevents overbooking)
    done = db.session.execute(
        update(Slot).where(Slot.id == slot.id, Slot.available_seats > 0,
                           Slot.status == "Available")
        .values(available_seats=Slot.available_seats - 1)).rowcount
    if done == 0:
        db.session.rollback()
        raise ApiError("Sorry, this slot is full", 409)
    db.session.refresh(slot)
    if slot.available_seats == 0:
        slot.status = "Full"
    booking = Booking(student_id=student.id, slot_id=slot.id, exam_id=exam.id)
    db.session.add(booking)
    notify(student.id, f"Booked {exam.name} on {slot.date} at {slot.start_time:%H:%M}", "success")
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError("You already have a booking for this examination", 409)
    cache.invalidate_exam(exam.id)
    return booking


def cancel_booking(booking, by_admin=False):
    if booking.status != "Booked":
        raise ApiError("Only active bookings can be cancelled")
    exam = booking.exam
    if booking.evaluation:
        raise ApiError("This booking has already been evaluated")
    if not by_admin and exam.booking_end and date.today() > exam.booking_end:
        raise ApiError("The booking deadline has passed, bookings can no longer be cancelled")
    booking.status = "Cancelled"
    booking.active_key = None
    booking.cancelled_at = datetime.utcnow()
    slot = booking.slot
    db.session.execute(update(Slot).where(Slot.id == slot.id)
                       .values(available_seats=Slot.available_seats + 1))
    db.session.refresh(slot)
    if slot.status == "Full":
        slot.status = "Available"
    notify(booking.student_id, f"Cancelled booking for {exam.name}", "info")
    db.session.commit()
    cache.invalidate_exam(exam.id)


def move_booking(booking, new_slot):
    """Admin reschedule: move an active booking to another slot of the same exam."""
    if booking.status != "Booked":
        raise ApiError("Only active bookings can be rescheduled")
    if new_slot.exam_id != booking.exam_id:
        raise ApiError("The new slot belongs to a different examination")
    if new_slot.id == booking.slot_id:
        raise ApiError("Booking is already in that slot")
    if new_slot.status != "Available" or new_slot.available_seats < 1:
        raise ApiError("The new slot has no free seats", 409)
    old = booking.slot
    old.available_seats += 1
    if old.status == "Full":
        old.status = "Available"
    new_slot.available_seats -= 1
    if new_slot.available_seats == 0:
        new_slot.status = "Full"
    booking.slot_id = new_slot.id
    notify(booking.student_id,
           f"Your {booking.exam.name} slot was moved to {new_slot.date} {new_slot.start_time:%H:%M}",
           "warning")
    db.session.commit()
    cache.invalidate_exam(booking.exam_id)


# ---------- marks ----------
def compute_total(exam, rubrics, marks_by_rubric):
    """Weighted total scaled to the exam's maximum marks.

    Each criterion contributes (marks / criterion_max) * weightage. The weighted
    percentage is then multiplied by the exam's maximum marks.
    """
    weight_sum = sum((r.weightage or 1.0) for r in rubrics) or 1.0
    pct = sum((marks_by_rubric[r.id] / r.max_marks) * (r.weightage or 1.0) for r in rubrics)
    return round(pct / weight_sum * exam.max_marks, 2)
