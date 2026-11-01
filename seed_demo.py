"""Optional: fill the database with demo data so you can try every screen.

    python seed_demo.py

Logins created (password for all: pass123):
    examiner1@emp.local, examiner2@emp.local, student1@emp.local, student2@emp.local
Admin login comes from config.py (admin@emp.local / admin123).
"""
from datetime import date, time, timedelta

from app import app
from extensions import db
from models import (Course, ExamExaminer, Examination, ExaminerProfile, Rubric, Slot, User)

with app.app_context():
    if Course.query.first():
        print("Demo data already present, nothing to do.")
        raise SystemExit

    def person(name, email, role, dept=None):
        u = User(name=name, email=email, role=role)
        u.set_password("pass123")
        if role == "examiner":
            u.examiner_profile = ExaminerProfile(department=dept, contact_details=email)
        db.session.add(u)
        return u

    e1 = person("Dr. Asha Rao", "examiner1@emp.local", "examiner", "Computer Science")
    e2 = person("Prof. Vikram Shah", "examiner2@emp.local", "examiner", "Information Technology")
    person("Riya Sen", "student1@emp.local", "student")
    person("Arjun Mehta", "student2@emp.local", "student")
    course = Course(code="CS201", name="Application Development 2", description="Flask and Vue")
    db.session.add(course)
    db.session.flush()

    today = date.today()
    exam = Examination(course_id=course.id, name="Project Viva", exam_type="Viva", duration_min=15,
                       max_marks=100, instructions="Bring your laptop and student ID.",
                       slot_create_start=today, slot_create_end=today + timedelta(days=7),
                       booking_start=today, booking_end=today + timedelta(days=14),
                       slot_creation_open=True, status="Slot Creation")
    db.session.add(exam)
    db.session.flush()
    for name, mx, w in [("Code understanding", 40, 40), ("Live demo", 30, 30),
                        ("Q&A", 20, 20), ("Presentation", 10, 10)]:
        db.session.add(Rubric(exam_id=exam.id, criterion_name=name, max_marks=mx, weightage=w))
    for ex in (e1, e2):
        db.session.add(ExamExaminer(exam_id=exam.id, examiner_id=ex.id))
    for i, ex in enumerate((e1, e2)):
        db.session.add(Slot(exam_id=exam.id, examiner_id=ex.id, date=today + timedelta(days=3),
                            start_time=time(10 + i, 0), end_time=time(10 + i, 45),
                            capacity=3, available_seats=3,
                            meeting_link="https://meet.google.com/demo"))
    db.session.commit()
    print("Demo data created. Open the Admin page to open booking for 'Project Viva'.")
