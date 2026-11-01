from datetime import date, datetime

from flask import Blueprint, g, jsonify, request

from decorators import protect
from extensions import db
from models import (Booking, Evaluation, EvaluationScore, ExamExaminer, Examination, Rubric,
                    Slot)
from services import cache
from services.booking import compute_total, fill_slot, notify
from utils import ApiError, as_float, as_int, parse_date, require

bp = Blueprint("examiner", __name__, url_prefix="/api/examiner")
protect(bp, "examiner")


def body():
    return request.get_json(silent=True) or {}


def my_exam(exam_id):
    exam = db.session.get(Examination, exam_id)
    if not exam or g.user.id not in exam.examiner_ids():
        raise ApiError("You are not assigned to this examination", 403)
    return exam


def my_slot(slot_id):
    slot = db.session.get(Slot, slot_id)
    if not slot:
        raise ApiError("Slot not found", 404)
    if slot.examiner_id != g.user.id:
        raise ApiError("This is not your slot", 403)
    return slot


def my_pending_query():
    return (Booking.query.join(Slot, Booking.slot_id == Slot.id)
            .filter(Slot.examiner_id == g.user.id, Booking.status == "Booked",
                    ~Booking.evaluation.has()))


@bp.get("/dashboard")
def dashboard():
    my_slots = Slot.query.filter(Slot.examiner_id == g.user.id, Slot.status != "Cancelled")
    booked = (Booking.query.join(Slot, Booking.slot_id == Slot.id)
              .filter(Slot.examiner_id == g.user.id, Booking.status != "Cancelled").count())
    exams = (Examination.query.join(ExamExaminer).filter(ExamExaminer.examiner_id == g.user.id)
             .order_by(Examination.id.desc()).all())
    return jsonify(assigned_exams=len(exams), slots=my_slots.count(), booked_students=booked,
                   pending_evaluations=my_pending_query().count(),
                   exams=[e.to_dict() for e in exams])


@bp.get("/exams")
def exams():
    rows = (Examination.query.join(ExamExaminer).filter(ExamExaminer.examiner_id == g.user.id)
            .order_by(Examination.id.desc()).all())
    return jsonify([e.to_dict(detail=True) for e in rows])


# ---------------------------------------------------------------- slots
@bp.get("/slots")
def list_slots():
    query = Slot.query.filter(Slot.examiner_id == g.user.id)
    if request.args.get("exam_id"):
        query = query.filter(Slot.exam_id == int(request.args["exam_id"]))
    return jsonify([s.to_dict() for s in query.order_by(Slot.date, Slot.start_time).all()])


@bp.post("/slots")
def create_slot():
    d = body()
    require(d, "exam_id", "date", "start_time", "end_time")
    exam = my_exam(as_int(d["exam_id"], "Examination"))
    if not exam.slot_creation_active:
        raise ApiError("Slot creation is not open for this examination right now")
    slot = Slot(exam_id=exam.id, examiner_id=g.user.id, capacity=1, available_seats=1)
    fill_slot(slot, d)
    if slot.date < date.today():
        raise ApiError("A slot cannot be created in the past")
    db.session.add(slot)
    db.session.commit()
    cache.invalidate_exam(exam.id)
    return jsonify(slot.to_dict()), 201


def _editable(slot):
    if slot.exam.booking_open or (slot.capacity - slot.available_seats) > 0:
        raise ApiError("Slots can only be changed before student booking begins "
                       "and while nobody has booked them", 409)


@bp.put("/slots/<int:sid>")
def update_slot(sid):
    slot = my_slot(sid)
    _editable(slot)
    if not slot.exam.slot_creation_active:
        raise ApiError("Slot creation period is not open for this examination")
    d = body()
    fill_slot(slot, {k: d[k] for k in ("date", "start_time", "end_time", "capacity", "meeting_link") if k in d})
    db.session.commit()
    cache.invalidate_exam(slot.exam_id)
    return jsonify(slot.to_dict())


@bp.delete("/slots/<int:sid>")
def delete_slot(sid):
    slot = my_slot(sid)
    _editable(slot)
    exam_id = slot.exam_id
    if Booking.query.filter_by(slot_id=sid).first():
        slot.status = "Cancelled"  # keep history of earlier cancelled bookings
    else:
        db.session.delete(slot)
    db.session.commit()
    cache.invalidate_exam(exam_id)
    return jsonify(message="Slot removed")


@bp.get("/slots/<int:sid>/students")
def slot_students(sid):
    slot = my_slot(sid)
    rows = Booking.query.filter(Booking.slot_id == sid, Booking.status != "Cancelled").all()
    out = []
    for b in rows:
        item = b.to_dict()
        item["evaluation"] = b.evaluation.to_dict() if b.evaluation else None
        out.append(item)
    return jsonify(slot=slot.to_dict(), students=out,
                   rubrics=[r.to_dict() for r in slot.exam.rubrics],
                   max_marks=slot.exam.max_marks)


# ---------------------------------------------------------------- evaluation
@bp.post("/bookings/<int:bid>/evaluate")
def evaluate(bid):
    booking = db.session.get(Booking, bid)
    if not booking:
        raise ApiError("Booking not found", 404)
    if booking.slot.examiner_id != g.user.id:
        raise ApiError("You can only evaluate students booked into your own slots", 403)
    if booking.status == "Cancelled":
        raise ApiError("This booking was cancelled")
    exam = booking.exam
    if exam.results_published:
        raise ApiError("Results are already published, evaluation is locked", 409)

    d = body()
    rubrics = exam.rubrics
    if not rubrics:
        raise ApiError("The Admin has not defined a rubric for this examination yet")
    given = {}
    for item in d.get("scores", []):
        rid = as_int(item.get("rubric_id"), "Rubric")
        given[rid] = as_float(item.get("marks"), "Marks", 0)
    marks = {}
    for r in rubrics:
        if r.id not in given:
            raise ApiError(f"Enter marks for '{r.criterion_name}'")
        if given[r.id] > r.max_marks:
            raise ApiError(f"Marks for '{r.criterion_name}' cannot exceed {r.max_marks:g}")
        marks[r.id] = given[r.id]
    total = compute_total(exam, rubrics, marks)

    ev = booking.evaluation or Evaluation(booking_id=booking.id, student_id=booking.student_id,
                                          examiner_id=g.user.id)
    ev.total_marks = total
    ev.remarks = (d.get("remarks") or "").strip()
    ev.evaluated_at = datetime.utcnow()
    ev.status = "Submitted"
    ev.scores.clear()
    for rid, m in marks.items():
        ev.scores.append(EvaluationScore(rubric_id=rid, marks=m))
    booking.status = "Completed"
    db.session.add(ev)
    db.session.commit()
    return jsonify(ev.to_dict())


# ---------------------------------------------------------------- exam status
@bp.put("/exams/<int:eid>/status")
def exam_status(eid):
    exam = my_exam(eid)
    if body().get("status") != "Completed":
        raise ApiError("Status must be Completed")
    pending = my_pending_query().filter(Booking.exam_id == eid).count()
    if pending:
        raise ApiError(f"{pending} booked student(s) still need to be evaluated", 409)
    for s in Slot.query.filter_by(exam_id=eid, examiner_id=g.user.id).all():
        if s.status != "Cancelled":
            s.status = "Completed"
    others_pending = (Booking.query.join(Slot, Booking.slot_id == Slot.id)
                      .filter(Booking.exam_id == eid, Booking.status == "Booked",
                              ~Booking.evaluation.has()).count())
    if not others_pending:
        exam.status = "Completed"
        exam.slot_creation_open = False
        exam.booking_open = False
    db.session.commit()
    cache.invalidate_exam(eid)
    return jsonify(exam.to_dict())
