# Examination Management Portal (EMP) V2

Flask API + Vue 3 (CDN) UI + Bootstrap, SQLite, JWT auth, Redis cache, Celery jobs.

## Run on Windows

1. Create and activate a virtual environment, then install packages:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Start Redis. Easiest: install WSL2 (Ubuntu), then inside it `sudo apt install redis-server` and `sudo service redis-server start`. Windows reaches it at `localhost:6379`. (Memurai also works.)
3. Start the web app (creates `emp.db` and the Admin automatically):
   ```
   python app.py
   ```
   Open http://127.0.0.1:5000
4. Optional demo data (examiners, students, a course and an exam):
   ```
   python seed_demo.py
   ```
5. In two more terminals (venv activated), start Celery:
   ```
   celery -A app.celery worker --pool=solo -l info
   celery -A app.celery beat -l info
   ```

The app still runs without Redis, but caching is skipped and the Celery jobs (CSV export, reminders, monthly report) will not start.

## Logins

| Role | Email | Password |
| --- | --- | --- |
| Admin (seeded in code) | admin@emp.local | admin123 |
| Examiner (after `seed_demo.py`) | examiner1@emp.local | pass123 |
| Student (after `seed_demo.py`) | student1@emp.local | pass123 |

Change the admin credentials in `config.py` (or the `ADMIN_EMAIL` / `ADMIN_PASSWORD` environment variables) before the first run.

## Demo walkthrough

1. Admin: create a course, create an examination with dates, add rubric criteria, add examiners, assign them, click **Open** under *Slot creation*.
2. Examiner: *My slots*, pick the examination, create slots.
3. Admin: click **Open** under *Booking* (this locks slot editing).
4. Student: register, *Examinations*, book a slot.
5. Examiner: open the slot, **Students**, **Evaluate** with the rubric.
6. Admin: **Publish results**. Student: *Results*, download scorecard.
7. Student: *My bookings*, **Export history (CSV)**.
8. Admin dashboard: **Send daily reminders now** / **Send monthly report now**.

Without SMTP settings, e-mails are saved as HTML files in `outbox/`. To send real e-mail set `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_SENDER` (and optionally `GCHAT_WEBHOOK`) as environment variables.

## Design notes (useful for the report and viva)

- `models.py`: one unified `User` table with a `role` column. Examiner extras live in `ExaminerProfile`. Examiner and student ids always refer to `users.id`.
- `ExamExaminer` is a link table for the examiners assigned to an exam.
- One booking per student per exam is enforced by the database: `Booking.active_key` is 1 for live bookings and NULL after a cancellation, with a unique constraint on `(student_id, exam_id, active_key)`.
- Overbooking is prevented by an atomic `UPDATE slots SET available_seats = available_seats - 1 WHERE available_seats > 0`. The slot becomes *Full* at zero and *Available* again after a cancellation.
- Marks: each criterion contributes `(marks / criterion max) * weightage`; the weighted percentage is scaled to the exam's maximum marks.
- Caching (Redis db 1): public exam list (5 min), slots per exam (60 s), rubrics per exam (10 min). Entries are cleared when data changes.
- Celery (Redis db 0): daily reminder (beat, 08:00 IST), monthly report (beat, 1st at 07:00), CSV export (triggered by the student), result e-mails (on publish).
- Roles are enforced per blueprint in `decorators.protect()`; the role is checked against the database on every request, not only in the JWT.

## Folder structure

```
app.py  config.py  extensions.py  models.py  decorators.py  utils.py  tasks.py  seed_demo.py
routes/    auth.py  common.py  admin.py  examiner.py  student.py
services/  cache.py  mailer.py  booking.py
templates/index.html            (only Jinja file: the Vue entry page)
static/css/custom.css
static/js/api.js  app.js
static/js/components/  common.js  admin.js  examiner.js  student.js
exports/ (generated CSVs)   outbox/ (saved e-mails)
```
