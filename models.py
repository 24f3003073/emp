from datetime import date, datetime

from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from utils import iso

EXAM_TYPES = ["Viva", "Practical", "Project Demo", "Assessment"]
EXAM_STATUSES = ["Draft", "Slot Creation", "Booking Open", "Closed", "Completed"]
ROLES = ["admin", "examiner", "student"]


def _in_window(start, end):
    today = date.today()
    if start and today < start:
        return False
    if end and today > end:
        return False
    return True


class User(db.Model):
    """Unified user table for admin, examiner and student."""
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, index=True)
    phone = db.Column(db.String(30))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    examiner_profile = db.relationship("ExaminerProfile", back_populates="user",
                                       uselist=False, cascade="all, delete-orphan")

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    def to_dict(self):
        d = dict(id=self.id, name=self.name, email=self.email, role=self.role,
                 phone=self.phone, is_active=self.is_active, created_at=iso(self.created_at))
        if self.role == "examiner" and self.examiner_profile:
            d.update(department=self.examiner_profile.department,
                     contact_details=self.examiner_profile.contact_details,
                     status=self.examiner_profile.status)
        return d


class ExaminerProfile(db.Model):
    __tablename__ = "examiner_profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    department = db.Column(db.String(120))
    contact_details = db.Column(db.String(255))
    status = db.Column(db.String(20), default="Active")
    user = db.relationship("User", back_populates="examiner_profile")


class Course(db.Model):
    __tablename__ = "courses"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default="Active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    exams = db.relationship("Examination", back_populates="course")

    def to_dict(self):
        return dict(id=self.id, code=self.code, name=self.name, description=self.description,
                    status=self.status, exam_count=len(self.exams))


class Examination(db.Model):
    __tablename__ = "examinations"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    exam_type = db.Column(db.String(30), nullable=False)
    duration_min = db.Column(db.Integer, nullable=False)
    max_marks = db.Column(db.Integer, nullable=False)
    instructions = db.Column(db.Text)
    slot_create_start = db.Column(db.Date)
    slot_create_end = db.Column(db.Date)
    booking_start = db.Column(db.Date)
    booking_end = db.Column(db.Date)
    slot_creation_open = db.Column(db.Boolean, default=False, nullable=False)
    booking_open = db.Column(db.Boolean, default=False, nullable=False)
    status = db.Column(db.String(20), default="Draft", nullable=False)
    results_published = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship("Course", back_populates="exams")
    rubrics = db.relationship("Rubric", cascade="all, delete-orphan", order_by="Rubric.id")
    slots = db.relationship("Slot", back_populates="exam", cascade="all, delete-orphan")
    examiner_links = db.relationship("ExamExaminer", cascade="all, delete-orphan")

    @property
    def slot_creation_active(self):
        return self.slot_creation_open and _in_window(self.slot_create_start, self.slot_create_end)

    @property
    def booking_active(self):
        return self.booking_open and _in_window(self.booking_start, self.booking_end)

    def refresh_status(self):
        if self.status == "Completed":
            return
        if self.booking_open:
            self.status = "Booking Open"
        elif self.slot_creation_open:
            self.status = "Slot Creation"
        elif self.slots:
            self.status = "Closed"
        else:
            self.status = "Draft"

    def examiner_ids(self):
        return [l.examiner_id for l in self.examiner_links]

    def to_dict(self, detail=False):
        d = dict(
            id=self.id, course_id=self.course_id,
            course_code=self.course.code if self.course else None,
            course_name=self.course.name if self.course else None,
            name=self.name, exam_type=self.exam_type, duration_min=self.duration_min,
            max_marks=self.max_marks, instructions=self.instructions,
            slot_create_start=iso(self.slot_create_start), slot_create_end=iso(self.slot_create_end),
            booking_start=iso(self.booking_start), booking_end=iso(self.booking_end),
            slot_creation_open=self.slot_creation_open, booking_open=self.booking_open,
            slot_creation_active=self.slot_creation_active, booking_active=self.booking_active,
            status=self.status, results_published=self.results_published,
        )
        if detail:
            d["rubrics"] = [r.to_dict() for r in self.rubrics]
            d["examiner_ids"] = self.examiner_ids()
            d["slot_count"] = len(self.slots)
        return d


class ExamExaminer(db.Model):
    """Link table: examiners assigned to an examination (examiner_id = users.id)."""
    __tablename__ = "exam_examiners"
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("examinations.id"), nullable=False)
    examiner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    examiner = db.relationship("User")
    __table_args__ = (db.UniqueConstraint("exam_id", "examiner_id"),)


class Rubric(db.Model):
    __tablename__ = "rubrics"
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("examinations.id"), nullable=False)
    criterion_name = db.Column(db.String(160), nullable=False)
    max_marks = db.Column(db.Float, nullable=False)
    weightage = db.Column(db.Float, default=1.0)
    description = db.Column(db.Text)

    def to_dict(self):
        return dict(id=self.id, exam_id=self.exam_id, criterion_name=self.criterion_name,
                    max_marks=self.max_marks, weightage=self.weightage, description=self.description)


class Slot(db.Model):
    __tablename__ = "slots"
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("examinations.id"), nullable=False)
    examiner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    capacity = db.Column(db.Integer, default=1, nullable=False)
    available_seats = db.Column(db.Integer, default=1, nullable=False)
    status = db.Column(db.String(20), default="Available", nullable=False)
    meeting_link = db.Column(db.String(255))

    exam = db.relationship("Examination", back_populates="slots")
    examiner = db.relationship("User")
    bookings = db.relationship("Booking", back_populates="slot")

    def to_dict(self):
        return dict(
            id=self.id, exam_id=self.exam_id, exam_name=self.exam.name,
            course_code=self.exam.course.code, examiner_id=self.examiner_id,
            examiner_name=self.examiner.name, date=iso(self.date),
            start_time=iso(self.start_time), end_time=iso(self.end_time),
            capacity=self.capacity, available_seats=self.available_seats,
            booked=self.capacity - self.available_seats, status=self.status,
            meeting_link=self.meeting_link,
        )


class Booking(db.Model):
    __tablename__ = "bookings"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey("slots.id"), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey("examinations.id"), nullable=False)
    booked_at = db.Column(db.DateTime, default=datetime.utcnow)
    cancelled_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="Booked", nullable=False)
    # active_key is 1 while the booking is live and NULL once cancelled. With the
    # unique constraint below this blocks duplicate bookings for the same exam in
    # the database itself, while still allowing a re-booking after a cancellation
    # (SQLite treats NULLs as distinct).
    active_key = db.Column(db.Integer, default=1)

    student = db.relationship("User")
    slot = db.relationship("Slot", back_populates="bookings")
    exam = db.relationship("Examination")
    evaluation = db.relationship("Evaluation", back_populates="booking", uselist=False)

    __table_args__ = (db.UniqueConstraint("student_id", "exam_id", "active_key",
                                          name="uq_one_active_booking_per_exam"),)

    def to_dict(self):
        s = self.slot
        return dict(
            id=self.id, student_id=self.student_id, student_name=self.student.name,
            student_email=self.student.email, slot_id=self.slot_id, exam_id=self.exam_id,
            exam_name=self.exam.name, course_code=self.exam.course.code,
            course_name=self.exam.course.name, exam_type=self.exam.exam_type,
            date=iso(s.date), start_time=iso(s.start_time), end_time=iso(s.end_time),
            examiner_id=s.examiner_id, examiner_name=s.examiner.name,
            meeting_link=s.meeting_link, status=self.status,
            booked_at=iso(self.booked_at), evaluated=self.evaluation is not None,
        )


class Evaluation(db.Model):
    __tablename__ = "evaluations"
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), unique=True, nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    examiner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    total_marks = db.Column(db.Float, nullable=False)
    remarks = db.Column(db.Text)
    evaluated_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="Submitted")

    booking = db.relationship("Booking", back_populates="evaluation")
    scores = db.relationship("EvaluationScore", cascade="all, delete-orphan")

    def to_dict(self):
        return dict(
            id=self.id, booking_id=self.booking_id, total_marks=self.total_marks,
            remarks=self.remarks, evaluated_at=iso(self.evaluated_at), status=self.status,
            scores=[dict(rubric_id=s.rubric_id, criterion_name=s.rubric.criterion_name,
                         max_marks=s.rubric.max_marks, marks=s.marks) for s in self.scores],
        )


class EvaluationScore(db.Model):
    __tablename__ = "evaluation_scores"
    id = db.Column(db.Integer, primary_key=True)
    evaluation_id = db.Column(db.Integer, db.ForeignKey("evaluations.id"), nullable=False)
    rubric_id = db.Column(db.Integer, db.ForeignKey("rubrics.id"), nullable=False)
    marks = db.Column(db.Float, nullable=False)
    rubric = db.relationship("Rubric")


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    message = db.Column(db.String(255), nullable=False)
    kind = db.Column(db.String(20), default="info")
    payload = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return dict(id=self.id, message=self.message, kind=self.kind, payload=self.payload,
                    is_read=self.is_read, created_at=iso(self.created_at))
