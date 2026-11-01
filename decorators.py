from flask import g, jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from extensions import db, jwt
from models import User


def current_user():
    return g.get("user")


def protect(blueprint, *roles):
    """Require a valid JWT and one of the given roles for every route in a blueprint."""

    @blueprint.before_request
    def _guard():
        verify_jwt_in_request()
        user = db.session.get(User, int(get_jwt_identity()))
        if not user or not user.is_active:
            return jsonify(error="Account not found or deactivated"), 403
        if roles and user.role not in roles:
            return jsonify(error="You do not have access to this resource"), 403
        g.user = user


def login_required_bp(blueprint):
    protect(blueprint)  # any logged-in role


@jwt.unauthorized_loader
def _missing(reason):
    return jsonify(error="Login required"), 401


@jwt.invalid_token_loader
def _invalid(reason):
    return jsonify(error="Invalid token, please log in again"), 401


@jwt.expired_token_loader
def _expired(header, payload):
    return jsonify(error="Session expired, please log in again"), 401
