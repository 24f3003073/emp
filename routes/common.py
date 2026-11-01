"""Endpoints open to every logged-in role: rubrics (cached) and notifications."""
from flask import Blueprint, g, jsonify

from config import Config
from decorators import protect
from extensions import db
from models import Examination, Notification
from services import cache
from utils import ApiError

bp = Blueprint("common", __name__, url_prefix="/api")
protect(bp)  # any valid role


@bp.get("/exams/<int:exam_id>/rubrics")
def rubrics(exam_id):
    exam = db.session.get(Examination, exam_id)
    if not exam:
        raise ApiError("Examination not found", 404)
    data = cache.cached(f"rubrics:exam:{exam_id}", Config.CACHE_TTL_RUBRICS,
                        lambda: [r.to_dict() for r in exam.rubrics])
    return jsonify(data)


@bp.get("/notifications")
def notifications():
    rows = (Notification.query.filter_by(user_id=g.user.id)
            .order_by(Notification.id.desc()).limit(30).all())
    return jsonify([n.to_dict() for n in rows])


@bp.post("/notifications/read")
def mark_read():
    Notification.query.filter_by(user_id=g.user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify(message="ok")
