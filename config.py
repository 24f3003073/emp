import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-secret")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-jwt-secret-at-least-32-chars-long")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)

    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "emp.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Redis: db 0 = Celery broker/result backend, db 1 = cache
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    CACHE_REDIS_URL = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379/1")

    # Cache expiry in seconds
    CACHE_TTL_EXAMS = 300
    CACHE_TTL_SLOTS = 60
    CACHE_TTL_RUBRICS = 600

    # Seeded admin (created programmatically, only one admin exists)
    ADMIN_NAME = os.getenv("ADMIN_NAME", "Administrator")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@emp.local")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

    # Email. If MAIL_SERVER is empty, emails are written to the outbox/ folder
    # so everything can be demoed without an SMTP account.
    MAIL_SERVER = os.getenv("MAIL_SERVER", "")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_SENDER = os.getenv("MAIL_SENDER", "emp@emp.local")
    OUTBOX_DIR = os.path.join(BASE_DIR, "outbox")
    EXPORT_DIR = os.path.join(BASE_DIR, "exports")

    # Optional Google Chat incoming webhook for reminders
    GCHAT_WEBHOOK = os.getenv("GCHAT_WEBHOOK", "")

    # Beat schedule (Asia/Kolkata)
    REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", "8"))
    REMINDER_MINUTE = int(os.getenv("REMINDER_MINUTE", "0"))
    CELERY_TIMEZONE = "Asia/Kolkata"

    
    # Update these two lines:
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    REDIS_CACHE_URL = os.environ.get('REDIS_CACHE_URL', 'redis://localhost:6379/1')