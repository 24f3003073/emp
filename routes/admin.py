from datetime import date, timedelta

from flask import Blueprint, g, jsonify, request
from sqlalchemy import func, or_

from decorators import protect
from extensions import db
from models import (EXAM_TYPES, Booking, Course, Evaluation, ExamExaminer, Examination,
                    ExaminerProfile, Notification, Rubric, Slot, User)
from services import cache
from services.booking import cancel_booking, fill_slot, move_booking, notify
from utils import ApiError, as_float, as_int, parse_date, require, valid_email

bp = Blueprint("admin", __name__, url_prefix="/api/admin")
protect(bp, "admin")

DATE_FIELDS = ["slot_create_start", "slot_create_end", "booking_start", "booking_end"]


def get_or_404(model, ident, label):
    obj = db.session.get(model, ident)
    if not obj:
        raise ApiError(f"{label} not found", 404)
    return obj


def body():
    return request.get_json(silent=True) or {}


# ---------------------------------------------------------------- dashboard
@bp.get("/dashboard")
def dashboard():
    return jsonify(
        courses=Course.query.count(),
        exams=Examination.query.count(),
        students=User.query.filter_by(role="student").count(),
        examiners=User.query.filter_by(role="examiner").count(),
        slots=Slot.query.count(),
        bookings=Booking.query.count(),
        active_bookings=Booking.query.filter_by(status="Booked").count(),
        pending_evaluations=Booking.query.filter(Booking.status == "Booked",
                                                 ~Booking.evaluation.has()).count(),
    )


@bp.get("/reports")
def reports():
    """Data for the ChartJS analytics on the admin dashboard."""
    popular = (db.session.query(Examination.name, func.count(Booking.id))
               .join(Booking, Booking.exam_id == Examination.id)
               .filter(Booking.status != "Cancelled")
               .group_by(Examination.id).order_by(func.count(Booking.id).desc()).limit(8).all())
    workload = (db.session.query(User.name, func.count(Booking.id))
                .join(Slot, Slot.examiner_id == User.id)
                .join(Booking, Booking.slot_id == Slot.id)
                .filter(Booking.status != "Cancelled")
                .group_by(User.id).order_by(func.count(Booking.id).desc()).limit(8).all())
    since = date.today() - timedelta(days=29)
    trend_rows = (db.session.query(func.date(Booking.booked_at), func.count(Booking.id))
                  .filter(func.date(Booking.booked_at) >= since.isoformat())
                  .group_by(func.date(Booking.booked_at)).all())
    trend = {str(d): c for d, c in trend_rows}
    days = [(since + timedelta(days=i)).isoformat() for i in range(30)]
    return jsonify(
        popular_exams=[dict(name=n, count=c) for n, c in popular],
        examiner_workload=[dict(name=n, count=c) for n, c in workload],
        booking_trend=dict(labels=days, values=[trend.get(d, 0) for d in days]),
    )


# ---------------------------------------------------------------- courses
@bp.get("/courses")
def list_courses():
    q = (request.args.get("q") or "").strip()
    query = Course.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Course.code.ilike(like), Course.name.ilike(like)))
    return jsonify([c.to_dict() for c in query.order_by(Course.code).all()])


@bp.post("/courses")
def create_course():
    d = body()
    require(d, "code", "name")
    code = d["code"].strip().upper()
    if Course.query.filter_by(code=code).first():
        raise ApiError("A course with this code already exists", 409)
    c = Course(code=code, name=d["name"].strip(), description=d.get("description"),
               status=d.get("status") or "Active")
    db.session.add(c)
    db.session.commit()
    return jsonify(c.to_dict()), 201


@bp.put("/courses/<int:cid>")
def update_course(cid):
    c = get_or_404(Course, cid, "Course")
    d = body()
    if "code" in d:
        code = d["code"].strip().upper()
        if not code:
            raise ApiError("Course code is required")
        other = Course.query.filter(Course.code == code, Course.id != cid).first()
        if other:
            raise ApiError("A course with this code already exists", 409)
        c.code = code
    if "name" in d:
        if not d["name"].strip():
            raise ApiError("Course name is required")
        c.name = d["name"].strip()
    if "description" in d:
        c.description = d["description"]
    if "status" in d:
        if d["status"] not in ("Active", "Inactive"):
            raise ApiError("Status must be Active or Inactive")
        c.status = d["status"]
    db.session.commit()
    cache.invalidate_exams()
    return jsonify(c.to_dict())


@bp.delete("/courses/<int:cid>")
def delete_course(cid):
    c = get_or_404(Course, cid, "Course")
    if c.exams:
        c.status = "Inactive"  # keep history; just hide the course
        db.session.commit()
        return jsonify(message="Course has examinations, so it was marked Inactive instead of deleted")
    db.session.delete(c)
    db.session.commit()
    return jsonify(message="Course deleted")


# ---------------------------------------------------------------- examinations
def fill_exam(exam, d):
    if "course_id" in d:
        get_or_404(Course, as_int(d["course_id"], "Course", 1), "Course")
        exam.course_id = int(d["course_id"])
    if "name" in d:
        if not str(d["name"]).strip():
            raise ApiError("Examination name is required")
        exam.name = d["name"].strip()
    if "exam_type" in d:
        if d["exam_type"] not in EXAM_TYPES:
            raise ApiError("Examination type must be one of: " + ", ".join(EXAM_TYPES))
        exam.exam_type = d["exam_type"]
    if "duration_min" in d:
        exam.duration_min = as_int(d["duration_min"], "Duration", 1)
    if "max_marks" in d:
        exam.max_marks = as_int(d["max_marks"], "Maximum marks", 1)
    if "instructions" in d:
        exam.instructions = d["instructions"]
    for f in DATE_FIELDS:
        if f in d:
            setattr(exam, f, parse_date(d[f]) if d[f] else None)
    if exam.slot_create_start and exam.slot_create_end and exam.slot_create_start > exam.slot_create_end:
        raise ApiError("Slot creation end date must be after the start date")
    if exam.booking_start and exam.booking_end and exam.booking_start > exam.booking_end:
        raise ApiError("Booking end date must be after the start date")


@bp.get("/exams")
def list_exams():
    q = (request.args.get("q") or "").strip()
    query = Examination.query.join(Course)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Examination.name.ilike(like), Course.name.ilike(like),
                                 Course.code.ilike(like)))
    if request.args.get("course_id"):
        query = query.filter(Examination.course_id == int(request.args["course_id"]))
    if request.args.get("status"):
        query = query.filter(Examination.status == request.args["status"])
    return jsonify([e.to_dict(detail=True) for e in query.order_by(Examination.id.desc()).all()])


@bp.post("/exams")
def create_exam():
    d = body()
    require(d, "course_id", "name", "exam_type", "duration_min", "max_marks")
    exam = Examination()
    fill_exam(exam, d)
    db.session.add(exam)
    db.session.commit()
    cache.invalidate_exams()
    return jsonify(exam.to_dict(detail=True)), 201


@bp.put("/exams/<int:eid>")
def update_exam(eid):
    exam = get_or_404(Examination, eid, "Examination")
    fill_exam(exam, body())
    db.session.commit()
    cache.invalidate_exam(eid)
    return jsonify(exam.to_dict(detail=True))


@bp.delete("/exams/<int:eid>")
def delete_exam(eid):
    exam = get_or_404(Examination, eid, "Examination")
    if Booking.query.filter_by(exam_id=eid).first():
        raise ApiError("This examination has bookings, so it cannot be deleted. "
                       "Set its status to Completed instead.", 409)
    db.session.delete(exam)
    db.session.commit()
    cache.invalidate_exam(eid)
    cache.invalidate_rubrics(eid)
    return jsonify(message="Examination deleted")


@bp.put("/exams/<int:eid>/status")
def set_exam_status(eid):
    exam = get_or_404(Examination, eid, "Examination")
    status = body().get("status")
    if status == "Completed":
        exam.status = "Completed"
        exam.slot_creation_open = False
        exam.booking_open = False
    elif status == "Reopen":
        exam.status = "Draft"
        exam.refresh_status()
    else:
        raise ApiError("Status must be Completed or Reopen")
    db.session.commit()
    cache.invalidate_exam(eid)
    return jsonify(exam.to_dict(detail=True))


@bp.post("/exams/<int:eid>/slot-creation")
def toggle_slot_creation(eid):
    exam = get_or_404(Examination, eid, "Examination")
    open_ = bool(body().get("open"))
    if exam.status == "Completed":
        raise ApiError("This examination is completed")
    if open_ and not exam.examiner_ids():
        raise ApiError("Assign at least one examiner before opening slot creation")
    exam.slot_creation_open = open_
    if open_:
        exam.booking_open = False
    exam.refresh_status()
    db.session.commit()
    cache.invalidate_exam(eid)
    return jsonify(exam.to_dict(detail=True))


@bp.post("/exams/<int:eid>/booking")
def toggle_booking(eid):
    exam = get_or_404(Examination, eid, "Examination")
    open_ = bool(body().get("open"))
    if exam.status == "Completed":
        raise ApiError("This examination is completed")
    if open_ and not Slot.query.filter(Slot.exam_id == eid, Slot.status != "Cancelled").first():
        raise ApiError("No slots exist yet, so booking cannot be opened")
    exam.booking_open = open_
    if open_:
        exam.slot_creation_open = False  # slots are locked once booking starts
    exam.refresh_status()
    db.session.commit()
    cache.invalidate_exam(eid)
    return jsonify(exam.to_dict(detail=True))


@bp.put("/exams/<int:eid>/examiners")
def assign_examiners(eid):
    exam = get_or_404(Examination, eid, "Examination")
    ids = {as_int(i, "Examiner id") for i in body().get("examiner_ids", [])}
    valid = {u.id for u in User.query.filter(User.id.in_(ids), User.role == "examiner").all()} if ids else set()
    if ids - valid:
        raise ApiError("One or more selected users are not examiners")
    current = set(exam.examiner_ids())
    for removed in current - ids:
        if Slot.query.filter_by(exam_id=eid, examiner_id=removed).filter(Slot.status != "Cancelled").first():
            raise ApiError("An examiner who already has slots for this exam cannot be removed", 409)
    for link in list(exam.examiner_links):
        if link.examiner_id not in ids:
            db.session.delete(link)
    for added in ids - current:
        db.session.add(ExamExaminer(exam_id=eid, examiner_id=added))
        notify(added, f"You were assigned to {exam.name}", "info")
    db.session.commit()
    return jsonify(exam.to_dict(detail=True))


@bp.post("/exams/<int:eid>/publish")
def publish_results(eid):
    exam = get_or_404(Examination, eid, "Examination")
    publish = body().get("publish", True)
    exam.results_published = bool(publish)
    evaluated = Evaluation.query.join(Booking).filter(Booking.exam_id == eid).all()
    pending = Booking.query.filter(Booking.exam_id == eid, Booking.status == "Booked",
                                   ~Booking.evaluation.has()).count()
    if publish:
        for ev in evaluated:
            notify(ev.student_id, f"Results published for {exam.name}", "success")
    db.session.commit()
    if publish:
        try:
            from tasks import send_result_emails
            send_result_emails.delay(eid)
        except Exception:
            pass  # emails are best effort; in-app notices are already saved
    return jsonify(published=exam.results_published, evaluated=len(evaluated), pending=pending)


# ---------------------------------------------------------------- rubrics
def fill_rubric(r, d):
    if "criterion_name" in d:
        if not str(d["criterion_name"]).strip():
            raise ApiError("Criterion name is required")
        r.criterion_name = d["criterion_name"].strip()
    if "max_marks" in d:
        r.max_marks = as_float(d["max_marks"], "Maximum marks", 0.01)
    if "weightage" in d and d["weightage"] not in (None, ""):
        r.weightage = as_float(d["weightage"], "Weightage", 0)
    if "description" in d:
        r.description = d["description"]


@bp.post("/exams/<int:eid>/rubrics")
def add_rubric(eid):
    get_or_404(Examination, eid, "Examination")
    d = body()
    require(d, "criterion_name", "max_marks")
    r = Rubric(exam_id=eid, weightage=1.0)
    fill_rubric(r, d)
    db.session.add(r)
    db.session.commit()
    cache.invalidate_rubrics(eid)
    return jsonify(r.to_dict()), 201


@bp.put("/rubrics/<int:rid>")
def update_rubric(rid):
    r = get_or_404(Rubric, rid, "Rubric")
    fill_rubric(r, body())
    db.session.commit()
    cache.invalidate_rubrics(r.exam_id)
    return jsonify(r.to_dict())


@bp.delete("/rubrics/<int:rid>")
def delete_rubric(rid):
    r = get_or_404(Rubric, rid, "Rubric")
    from models import EvaluationScore
    if EvaluationScore.query.filter_by(rubric_id=rid).first():
        raise ApiError("This criterion is already used in evaluations", 409)
    eid = r.exam_id
    db.session.delete(r)
    db.session.commit()
    cache.invalidate_rubrics(eid)
    return jsonify(message="Criterion removed")


# ---------------------------------------------------------------- examiners & students
@bp.get("/examiners")
def list_examiners():
    q = (request.args.get("q") or "").strip()
    query = User.query.filter_by(role="examiner")
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.name.ilike(like), User.email.ilike(like)))
    return jsonify([u.to_dict() for u in query.order_by(User.name).all()])


@bp.post("/examiners")
def create_examiner():
    d = body()
    require(d, "name", "email", "password")
    email = d["email"].strip().lower()
    if not valid_email(email):
        raise ApiError("Enter a valid email address")
    if len(d["password"]) < 6:
        raise ApiError("Password must be at least 6 characters")
    if User.query.filter_by(email=email).first():
        raise ApiError("An account with this email already exists", 409)
    u = User(name=d["name"].strip(), email=email, role="examiner", phone=d.get("phone"))
    u.set_password(d["password"])
    u.examiner_profile = ExaminerProfile(department=d.get("department"),
                                         contact_details=d.get("contact_details"))
    db.session.add(u)
    db.session.commit()
    return jsonify(u.to_dict()), 201


@bp.put("/examiners/<int:uid>")
def update_examiner(uid):
    u = get_or_404(User, uid, "Examiner")
    if u.role != "examiner":
        raise ApiError("Not an examiner", 404)
    d = body()
    if "name" in d and str(d["name"]).strip():
        u.name = d["name"].strip()
    if "phone" in d:
        u.phone = d["phone"]
    if d.get("password"):
        if len(d["password"]) < 6:
            raise ApiError("Password must be at least 6 characters")
        u.set_password(d["password"])
    prof = u.examiner_profile or ExaminerProfile(user=u)
    for f in ("department", "contact_details"):
        if f in d:
            setattr(prof, f, d[f])
    if "is_active" in d:
        u.is_active = bool(d["is_active"])
        prof.status = "Active" if u.is_active else "Inactive"
    db.session.commit()
    return jsonify(u.to_dict())


@bp.get("/students")
def list_students():
    q = (request.args.get("q") or "").strip()
    query = User.query.filter_by(role="student")
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.name.ilike(like), User.email.ilike(like), User.phone.ilike(like)))
    rows = query.order_by(User.name).all()
    counts = dict(db.session.query(Booking.student_id, func.count(Booking.id)).group_by(Booking.student_id).all())
    return jsonify([dict(u.to_dict(), bookings=counts.get(u.id, 0)) for u in rows])


@bp.put("/students/<int:uid>")
def update_student(uid):
    u = get_or_404(User, uid, "Student")
    if u.role != "student":
        raise ApiError("Not a student", 404)
    d = body()
    if "is_active" in d:
        u.is_active = bool(d["is_active"])
    db.session.commit()
    return jsonify(u.to_dict())


# ---------------------------------------------------------------- slots & bookings
@bp.get("/slots")
def list_slots():
    query = Slot.query
    if request.args.get("exam_id"):
        query = query.filter(Slot.exam_id == int(request.args["exam_id"]))
    if request.args.get("examiner_id"):
        query = query.filter(Slot.examiner_id == int(request.args["examiner_id"]))
    if request.args.get("date"):
        query = query.filter(Slot.date == parse_date(request.args["date"]))
    return jsonify([s.to_dict() for s in query.order_by(Slot.date, Slot.start_time).all()])


@bp.put("/slots/<int:sid>")
def reschedule_slot(sid):
    """Exceptional change of a slot's date, time, capacity or link."""
    slot = get_or_404(Slot, sid, "Slot")
    d = body()
    fill_slot(slot, {k: d[k] for k in ("date", "start_time", "end_time", "capacity", "meeting_link") if k in d})
    for b in Booking.query.filter_by(slot_id=sid, status="Booked").all():
        notify(b.student_id, f"Your {slot.exam.name} slot changed to {slot.date} {slot.start_time:%H:%M}", "warning")
    db.session.commit()
    cache.invalidate_exam(slot.exam_id)
    return jsonify(slot.to_dict())


@bp.put("/slots/<int:sid>/examiner")
def change_examiner(sid):
    slot = get_or_404(Slot, sid, "Slot")
    require(body(), "examiner_id")
    new = get_or_404(User, as_int(body()["examiner_id"], "Examiner"), "Examiner")
    if new.role != "examiner" or not new.is_active:
        raise ApiError("Select an active examiner")
    slot.examiner_id = new.id
    if new.id not in slot.exam.examiner_ids():
        db.session.add(ExamExaminer(exam_id=slot.exam_id, examiner_id=new.id))
    fill_slot(slot, {})  # re-check for time clashes with the new examiner
    for b in Booking.query.filter_by(slot_id=sid, status="Booked").all():
        notify(b.student_id, f"Your examiner for {slot.exam.name} is now {new.name}", "warning")
    db.session.commit()
    cache.invalidate_exam(slot.exam_id)
    return jsonify(slot.to_dict())


@bp.get("/bookings")
def list_bookings():
    q = (request.args.get("q") or "").strip()
    query = (Booking.query.join(User, Booking.student_id == User.id)
             .join(Examination, Booking.exam_id == Examination.id))
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.name.ilike(like), User.email.ilike(like),
                                 Examination.name.ilike(like)))
    if request.args.get("exam_id"):
        query = query.filter(Booking.exam_id == int(request.args["exam_id"]))
    if request.args.get("status"):
        query = query.filter(Booking.status == request.args["status"])
    return jsonify([b.to_dict() for b in query.order_by(Booking.id.desc()).all()])


@bp.put("/bookings/<int:bid>/reschedule")
def reschedule_booking(bid):
    b = get_or_404(Booking, bid, "Booking")
    require(body(), "slot_id")
    move_booking(b, get_or_404(Slot, as_int(body()["slot_id"], "Slot"), "Slot"))
    return jsonify(b.to_dict())


@bp.delete("/bookings/<int:bid>")
def admin_cancel_booking(bid):
    b = get_or_404(Booking, bid, "Booking")
    cancel_booking(b, by_admin=True)
    return jsonify(b.to_dict())


# ---------------------------------------------------------------- search & jobs
@bp.get("/search")
def search():
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        raise ApiError("Type at least 2 characters to search")
    like = f"%{q}%"
    people = lambda role: [u.to_dict() for u in User.query.filter(
        User.role == role, or_(User.name.ilike(like), User.email.ilike(like))).limit(20)]
    exams = Examination.query.join(Course).filter(
        or_(Examination.name.ilike(like), Course.name.ilike(like), Course.code.ilike(like))).limit(20)
    bookings = (Booking.query.join(User, Booking.student_id == User.id)
                .join(Examination, Booking.exam_id == Examination.id)
                .filter(or_(User.name.ilike(like), Examination.name.ilike(like))).limit(20))
    return jsonify(students=people("student"), examiners=people("examiner"),
                   exams=[e.to_dict() for e in exams], bookings=[b.to_dict() for b in bookings])


@bp.post("/jobs/<name>")
def run_job(name):
    """Queue a Celery job on demand (handy for demos): reminders or monthly-report."""
    try:
        import tasks
        if name == "reminders":
            r = tasks.daily_reminders.delay()
        elif name == "monthly-report":
            r = tasks.monthly_report.delay()
        else:
            raise ApiError("Unknown job", 404)
    except ApiError:
        raise
    except Exception:
        raise ApiError("Could not queue the job. Is Redis running?", 503)
    return jsonify(message="Job queued", task_id=r.id)
