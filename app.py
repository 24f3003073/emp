"""Examination Management Portal (EMP) - Flask application entry point.

Run the web app:      python app.py
Run Celery worker:    celery -A app.celery worker --pool=solo -l info
Run Celery beat:      celery -A app.celery beat -l info
"""
import os

from flask import Flask, jsonify, render_template
from werkzeug.exceptions import HTTPException

from config import Config
from extensions import celery, db, jwt
from utils import ApiError


def configure_celery(app):
    celery.conf.update(
        broker_url=app.config["CELERY_BROKER_URL"],
        result_backend=app.config["CELERY_RESULT_BACKEND"],
        timezone=app.config["CELERY_TIMEZONE"],
        enable_utc=False,
        broker_connection_retry_on_startup=True,
    )

    class ContextTask(celery.Task):
        """Run every task inside the Flask app context (database access)."""
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    import tasks  # registers the tasks
    celery.conf.beat_schedule = tasks.beat_schedule(app.config)


def seed_admin(app):
    """The single Admin is created in code; there is no admin registration."""
    from models import User
    if not User.query.filter_by(role="admin").first():
        admin = User(name=app.config["ADMIN_NAME"], email=app.config["ADMIN_EMAIL"].lower(), role="admin")
        admin.set_password(app.config["ADMIN_PASSWORD"])
        db.session.add(admin)
        db.session.commit()


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    os.makedirs(app.config["EXPORT_DIR"], exist_ok=True)
    os.makedirs(app.config["OUTBOX_DIR"], exist_ok=True)

    db.init_app(app)
    jwt.init_app(app)
    configure_celery(app)

    from routes import admin, auth, common, examiner, student
    for module in (auth, common, admin, examiner, student):
        app.register_blueprint(module.bp)

    @app.errorhandler(ApiError)
    def handle_api_error(e):
        db.session.rollback()
        return jsonify(error=e.message), e.status

    @app.errorhandler(HTTPException)
    def handle_http(e):
        return jsonify(error=e.description), e.code

    @app.errorhandler(Exception)
    def handle_unexpected(e):
        db.session.rollback()
        app.logger.exception(e)
        return jsonify(error="Something went wrong on the server"), 500

    @app.get("/")
    def index():
        # Only the entry page is a Jinja template; the whole UI is built by Vue.
        return render_template("index.html")

    with app.app_context():
        db.create_all()  # tables are created programmatically
        seed_admin(app)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
