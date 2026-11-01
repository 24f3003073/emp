from flask import Blueprint, g, jsonify, request
from flask_jwt_extended import create_access_token, verify_jwt_in_request, get_jwt_identity

from extensions import db
from models import ExaminerProfile, User
from utils import ApiError, require, valid_email

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/register")
def register():
    """Student self-registration. Admin and examiners can never register here."""
    d = request.get_json(silent=True) or {}
    require(d, "name", "email", "password")
    email = d["email"].strip().lower()
    if not valid_email(email):
        raise ApiError("Enter a valid email address")
    if len(d["password"]) < 6:
        raise ApiError("Password must be at least 6 characters")
    if User.query.filter_by(email=email).first():
        raise ApiError("An account with this email already exists", 409)
    user = User(name=d["name"].strip(), email=email, role="student",
                phone=(d.get("phone") or "").strip() or None)
    user.set_password(d["password"])
    db.session.add(user)
    db.session.commit()
    return jsonify(message="Registration successful, please log in"), 201


@bp.post("/login")
def login():
    d = request.get_json(silent=True) or {}
    require(d, "email", "password")
    user = User.query.filter_by(email=d["email"].strip().lower()).first()
    if not user or not user.check_password(d["password"]):
        raise ApiError("Invalid email or password", 401)
    if not user.is_active:
        raise ApiError("This account has been deactivated", 403)
    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    return jsonify(token=token, role=user.role, name=user.name, id=user.id)


def _me():
    verify_jwt_in_request()
    user = db.session.get(User, int(get_jwt_identity()))
    if not user or not user.is_active:
        raise ApiError("Account not found or deactivated", 403)
    return user


@bp.get("/profile")
def get_profile():
    return jsonify(_me().to_dict())


@bp.put("/profile")
def update_profile():
    user = _me()
    d = request.get_json(silent=True) or {}
    if "name" in d:
        if not str(d["name"]).strip():
            raise ApiError("Name cannot be empty")
        user.name = d["name"].strip()
    if "phone" in d:
        user.phone = (d["phone"] or "").strip() or None
    if d.get("password"):
        if len(d["password"]) < 6:
            raise ApiError("Password must be at least 6 characters")
        user.set_password(d["password"])
    if user.role == "examiner":
        prof = user.examiner_profile or ExaminerProfile(user=user)
        if "department" in d:
            prof.department = d["department"]
        if "contact_details" in d:
            prof.contact_details = d["contact_details"]
    db.session.commit()
    return jsonify(user.to_dict())
