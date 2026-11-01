"""Thin Redis cache. If Redis is unreachable every call quietly falls back to
the database, so the app still works (just slower) without Redis running."""
import json
import time

import redis
from flask import current_app

_client = None
_down_until = 0.0
PREFIX = "emp:"


def _r():
    global _client
    if _client is None:
        _client = redis.Redis.from_url(current_app.config["CACHE_REDIS_URL"],
                                       socket_connect_timeout=0.5, socket_timeout=0.5,
                                       decode_responses=True)
    return _client


def _guard(fn):
    global _down_until
    if time.time() < _down_until:
        return None
    try:
        return fn()
    except Exception:
        _down_until = time.time() + 10  # skip Redis for 10s after a failure
        return None


def get(key):
    raw = _guard(lambda: _r().get(PREFIX + key))
    return json.loads(raw) if raw else None


def put(key, value, ttl):
    _guard(lambda: _r().setex(PREFIX + key, ttl, json.dumps(value)))


def delete(*keys):
    if keys:
        _guard(lambda: _r().delete(*[PREFIX + k for k in keys]))


def delete_prefix(prefix):
    def run():
        for k in _r().scan_iter(match=PREFIX + prefix + "*"):
            _r().delete(k)
    _guard(run)


def cached(key, ttl, builder):
    """Return cached value or build it, store it with an expiry and return it."""
    value = get(key)
    if value is not None:
        return value
    value = builder()
    put(key, value, ttl)
    return value


def invalidate_exams():
    delete_prefix("exams:")


def invalidate_exam(exam_id):
    invalidate_exams()
    delete(f"slots:exam:{exam_id}")


def invalidate_rubrics(exam_id):
    delete(f"rubrics:exam:{exam_id}")
