"""Celery jobs: daily reminders, monthly report, CSV export, result emails.

Run (Windows):
    celery -A app.celery worker --pool=solo -l info
    celery -A app.celery beat -l info
"""
import csv
import os
from collections import defaultdict
from datetime import date, datetime, timedelta

from celery.schedules import crontab
from flask import current_app
from sqlalchemy import func

from extensions import celery, db
from models import Booking, Evaluation, Examination, Slot, User
from services.booking import notify
from services.mailer import send_email, send_gchat


def beat_schedule(cfg):
    return {
        "daily-exam-reminders": {
            "task": "tasks.daily_reminders",
            "schedule": crontab(hour=cfg["REMINDER_HOUR"], minute=cfg["REMINDER_MINUTE"]),
        },
        "monthly-exam-report": {
            "task": "tasks.monthly_report",
            "schedule": crontab(day_of_month=1, hour=7, minute=0),
        },
    }


# ---------------------------------------------------------------- a. daily reminder
@celery.task(name="tasks.daily_reminders")
def daily_reminders():
    """Remind students about exams happening today or tomorrow (email + Google Chat)."""
    today, tomorrow = date.today(), date.today() + timedelta(days=1)
    rows = (Booking.query.join(Slot, Booking.slot_id == Slot.id)
            .filter(Booking.status == "Booked", Slot.date.in_([today, tomorrow])).all())
    per_student = defaultdict(list)
    for b in rows:
        per_student[b.student_id].append(b)
    sent = 0
    for sid, bookings in per_student.items():
        student = db.session.get(User, sid)
        lines_html, lines_text = [], []
        for b in bookings:
            s, e = b.slot, b.exam
            when = "Today" if s.date == today else "Tomorrow"
            info = (f"{e.name} ({e.course.code}) - {when}, {s.date} {s.start_time:%H:%M}-{s.end_time:%H:%M}, "
                    f"Examiner: {s.examiner.name}")
            lines_text.append(info + (f", Instructions: {e.instructions}" if e.instructions else ""))
            lines_html.append(f"<li><b>{e.name}</b> ({e.course.code})<br>{when}, {s.date} "
                              f"{s.start_time:%H:%M}-{s.end_time:%H:%M}<br>Examiner: {s.examiner.name}<br>"
                              f"Instructions: {e.instructions or 'None'}</li>")
        html = f"<h3>Hi {student.name}, exam reminder</h3><ul>{''.join(lines_html)}</ul>"
        send_email(student.email, "Examination reminder", html)
        try:
            send_gchat(f"Reminder for {student.name}:\n" + "\n".join(lines_text))
        except Exception:
            pass
        notify(student.id, f"Reminder: {len(bookings)} examination(s) coming up", "warning")
        sent += 1
    db.session.commit()
    return f"{sent} reminder(s) sent"


# ---------------------------------------------------------------- b. monthly report
def build_report_html(year, month):
    start = date(year, month, 1)
    end = date(year + (month == 12), (month % 12) + 1, 1)
    in_month = (Slot.date >= start) & (Slot.date < end)
    conducted = (db.session.query(func.count(func.distinct(Slot.exam_id)))
                 .join(Booking, Booking.slot_id == Slot.id)
                 .filter(in_month, Booking.status.in_(["Booked", "Completed"])).scalar())
    evaluated = (Evaluation.query.join(Booking).join(Slot, Booking.slot_id == Slot.id)
                 .filter(in_month).count())
    completed = Booking.query.join(Slot, Booking.slot_id == Slot.id) \
        .filter(in_month, Booking.status == "Completed").count()
    pending = (Booking.query.join(Slot, Booking.slot_id == Slot.id)
               .filter(in_month, Booking.status == "Booked", ~Booking.evaluation.has()).count())
    active = (db.session.query(User.name, func.count(Evaluation.id))
              .join(Evaluation, Evaluation.examiner_id == User.id)
              .join(Booking, Evaluation.booking_id == Booking.id)
              .join(Slot, Booking.slot_id == Slot.id).filter(in_month)
              .group_by(User.id).order_by(func.count(Evaluation.id).desc()).limit(5).all())
    rows = "".join(f"<tr><td>{n}</td><td>{c}</td></tr>" for n, c in active) or \
        "<tr><td colspan='2'>No evaluations this month</td></tr>"
    return f"""<html><body style="font-family:Arial">
<h2>Monthly Examination Report - {start:%B %Y}</h2>
<table border="1" cellpadding="6" cellspacing="0">
<tr><td>Examinations conducted</td><td>{conducted}</td></tr>
<tr><td>Students evaluated</td><td>{evaluated}</td></tr>
<tr><td>Completed bookings</td><td>{completed}</td></tr>
<tr><td>Pending evaluations</td><td>{pending}</td></tr></table>
<h3>Most active examiners</h3>
<table border="1" cellpadding="6" cellspacing="0"><tr><th>Examiner</th><th>Evaluations</th></tr>{rows}</table>
</body></html>"""


@celery.task(name="tasks.monthly_report")
def monthly_report():
    """Report for the previous month, e-mailed to the Admin as HTML."""
    first_this = date.today().replace(day=1)
    last_month = first_this - timedelta(days=1)
    html = build_report_html(last_month.year, last_month.month)
    admin = User.query.filter_by(role="admin").first()
    send_email(admin.email, f"Monthly examination report - {last_month:%B %Y}", html)
    return f"report for {last_month:%B %Y} sent"


# ---------------------------------------------------------------- c. CSV export
@celery.task(name="tasks.export_history_csv")
def export_history_csv(user_id):
    """User-triggered job: write the student's examination history to CSV, then alert them."""
    rows = (Booking.query.filter_by(student_id=user_id).order_by(Booking.id).all())
    os.makedirs(current_app.config["EXPORT_DIR"], exist_ok=True)
    filename = f"history_{user_id}_{datetime.now():%Y%m%d%H%M%S}.csv"
    path = os.path.join(current_app.config["EXPORT_DIR"], filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Student ID", "Examination Name", "Course", "Examination Date", "Examiner",
                    "Marks Obtained", "Booking Status"])
        for b in rows:
            ev = b.evaluation
            marks = ev.total_marks if (ev and b.exam.results_published) else ""
            w.writerow([b.student_id, b.exam.name, f"{b.exam.course.code} {b.exam.course.name}",
                        b.slot.date.isoformat(), b.slot.examiner.name, marks, b.status])
    notify(user_id, "Your examination history export is ready to download", "export", filename)
    db.session.commit()
    student = db.session.get(User, user_id)
    send_email(student.email, "Your examination history export is ready",
               "<p>Your CSV export is ready. Log in to the portal to download it.</p>")
    return filename


# ---------------------------------------------------------------- result e-mails
@celery.task(name="tasks.send_result_emails")
def send_result_emails(exam_id):
    exam = db.session.get(Examination, exam_id)
    evals = Evaluation.query.join(Booking).filter(Booking.exam_id == exam_id).all()
    for ev in evals:
        student = db.session.get(User, ev.student_id)
        send_email(student.email, f"Results published: {exam.name}",
                   f"<p>Hi {student.name}, your result for <b>{exam.name}</b> is published. "
                   f"Log in to view your marks and the examiner's feedback.</p>")
    return f"{len(evals)} email(s) sent"
