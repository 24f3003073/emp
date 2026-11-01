import os
from datetime import date

from flask import Blueprint, Response, current_app, g, jsonify, request, send_file

from config import Config
from decorators import protect
from extensions import db
from models import Booking, Evaluation, Examination, Slot
from services import cache
from services.booking import book_slot, cancel_booking
from utils import ApiError, as_int, require

bp = Blueprint("student", __name__, url_prefix="/api/student")
protect(bp, "student")


def body():
    return request.get_json(silent=True) or {}


def public_exams():
    """All examinations visible to students (everything except Draft), cached in Redis."""
    def build():
        out = []
        rows = Examination.query.filter(Examination.status != "Draft").order_by(Examination.id.desc()).all()
        for e in rows:
            d = e.to_dict()
            d["seats_left"] = sum(s.available_seats for s in e.slots if s.status == "Available")
            out.append(d)
        return out
    return cache.cached("exams:public", Config.CACHE_TTL_EXAMS, build)


def my_active_bookings():
    rows = Booking.query.filter_by(student_id=g.user.id, active_key=1).all()
    return {b.exam_id: b for b in rows}


@bp.get("/exams")
def list_exams():
    q = (request.args.get("q") or "").strip().lower()
    etype, course_id, status = request.args.get("type"), request.args.get("course_id"), request.args.get("status")
    mine = my_active_bookings()
    out = []
    for e in public_exams():
        if q and q not in (e["name"] + " " + e["course_name"] + " " + e["course_code"]).lower():
            continue
        if etype and e["exam_type"] != etype:
            continue
        if course_id and str(e["course_id"]) != course_id:
            continue
        if status and e["status"] != status:
            continue
        b = mine.get(e["id"])
        out.append(dict(e, my_booking=b.to_dict() if b else None,
                        results_visible=e["results_published"]))
    return jsonify(out)


@bp.get("/exams/<int:eid>/slots")
def exam_slots(eid):
    exam = db.session.get(Examination, eid)
    if not exam or exam.status == "Draft":
        raise ApiError("Examination not found", 404)

    def build():
        rows = Slot.query.filter(Slot.exam_id == eid, Slot.status.in_(["Available", "Full"])) \
            .order_by(Slot.date, Slot.start_time).all()
        return [s.to_dict() for s in rows]
    return jsonify(cache.cached(f"slots:exam:{eid}", Config.CACHE_TTL_SLOTS, build))


@bp.post("/bookings")
def create_booking():
    d = body()
    require(d, "slot_id")
    slot = db.session.get(Slot, as_int(d["slot_id"], "Slot"))
    if not slot:
        raise ApiError("Slot not found", 404)
    return jsonify(book_slot(g.user, slot).to_dict()), 201


@bp.delete("/bookings/<int:bid>")
def delete_booking(bid):
    b = db.session.get(Booking, bid)
    if not b or b.student_id != g.user.id:
        raise ApiError("Booking not found", 404)
    cancel_booking(b)
    return jsonify(b.to_dict())


@bp.get("/history")
def history():
    rows = (Booking.query.filter_by(student_id=g.user.id)
            .order_by(Booking.id.desc()).all())
    out = []
    for b in rows:
        item = b.to_dict()
        ev = b.evaluation
        published = b.exam.results_published
        item["max_marks"] = b.exam.max_marks
        item["marks"] = ev.total_marks if (ev and published) else None
        item["result_published"] = published and ev is not None
        out.append(item)
    return jsonify(out)


@bp.get("/results")
def results():
    rows = (Evaluation.query.join(Booking).join(Examination, Booking.exam_id == Examination.id)
            .filter(Evaluation.student_id == g.user.id, Examination.results_published.is_(True))
            .order_by(Evaluation.id.desc()).all())
    out = []
    for ev in rows:
        b = ev.booking
        out.append(dict(ev.to_dict(), exam_name=b.exam.name, course_code=b.exam.course.code,
                        course_name=b.exam.course.name, max_marks=b.exam.max_marks,
                        examiner_name=b.slot.examiner.name, date=b.slot.date.isoformat()))
    return jsonify(out)


@bp.get("/results/<int:booking_id>/scorecard")
def scorecard(booking_id):
    """Downloadable HTML scorecard for a published result."""
    ev = Evaluation.query.filter_by(booking_id=booking_id, student_id=g.user.id).first()
    if not ev or not ev.booking.exam.results_published:
        raise ApiError("Result not available", 404)
    b, e = ev.booking, ev.booking.exam
    rows = "".join(f"<tr><td>{s['criterion_name']}</td><td>{s['marks']:g} / {s['max_marks']:g}</td></tr>"
                   for s in ev.to_dict()["scores"])
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Scorecard</title>
<style>body{{font-family:Arial;max-width:640px;margin:30px auto}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #999;padding:6px;text-align:left}}</style></head><body>
<h2>Examination Scorecard</h2>
<p><b>Student:</b> {g.user.name} ({g.user.email})<br><b>Course:</b> {e.course.code} {e.course.name}<br>
<b>Examination:</b> {e.name} ({e.exam_type})<br><b>Date:</b> {b.slot.date}<br>
<b>Examiner:</b> {b.slot.examiner.name}</p>
<table><tr><th>Criterion</th><th>Marks</th></tr>{rows}</table>
<h3>Total: {ev.total_marks:g} / {e.max_marks}</h3><p><b>Remarks:</b> {ev.remarks or '-'}</p></body></html>"""
    return Response(html, mimetype="text/html",
                    headers={"Content-Disposition": f"attachment; filename=scorecard_{booking_id}.html"})


@bp.get("/dashboard")
def dashboard():
    today = date.today()
    mine = my_active_bookings()
    exams = public_exams()
    available = [e for e in exams if e["booking_active"] and e["id"] not in mine]
    slots = []
    for e in available:
        rows = Slot.query.filter(Slot.exam_id == e["id"], Slot.status == "Available") \
            .order_by(Slot.date, Slot.start_time).limit(5).all()
        slots.extend(s.to_dict() for s in rows)
    upcoming = [b.to_dict() for b in sorted(mine.values(), key=lambda x: (x.slot.date, x.slot.start_time))
                if b.slot.date >= today and b.status == "Booked"]
    results = (Evaluation.query.join(Booking).join(Examination, Booking.exam_id == Examination.id)
               .filter(Evaluation.student_id == g.user.id, Examination.results_published.is_(True)).all())
    return jsonify(
        available_exams=available, available_slots=slots, upcoming=upcoming,
        booked=[b.to_dict() for b in mine.values()],
        results=[dict(ev.to_dict(), exam_name=ev.booking.exam.name, max_marks=ev.booking.exam.max_marks)
                 for ev in results],
    )


# ---------------------------------------------------------------- CSV export job
@bp.post("/export")
def start_export():
    try:
        from tasks import export_history_csv
        result = export_history_csv.delay(g.user.id)
    except Exception:
        raise ApiError("Could not start the export job. Make sure Redis and the Celery worker are running.", 503)
    return jsonify(message="Export started, you will get an alert when it is ready", task_id=result.id), 202


@bp.get("/export/<task_id>")
def export_status(task_id):
    try:
        from extensions import celery
        res = celery.AsyncResult(task_id)
        state = res.state
        filename = res.result if state == "SUCCESS" else None
    except Exception:
        raise ApiError("Could not read the job status. Is Redis running?", 503)
    return jsonify(state=state, filename=filename)


@bp.get("/export/download/<filename>")
def export_download(filename):
    safe = os.path.basename(filename)
    if not safe.startswith(f"history_{g.user.id}_") or not safe.endswith(".csv"):
        raise ApiError("File not found", 404)
    path = os.path.join(current_app.config["EXPORT_DIR"], safe)
    if not os.path.exists(path):
        raise ApiError("File not found", 404)
    return send_file(path, mimetype="text/csv", as_attachment=True, download_name=safe)
