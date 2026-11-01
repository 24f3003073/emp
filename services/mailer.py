import json
import os
import smtplib
import urllib.request
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app


def send_email(to, subject, html):
    """Send via SMTP when configured, otherwise save the mail in outbox/."""
    cfg = current_app.config
    if not cfg["MAIL_SERVER"]:
        os.makedirs(cfg["OUTBOX_DIR"], exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe = "".join(c if c.isalnum() else "_" for c in to)
        path = os.path.join(cfg["OUTBOX_DIR"], f"{stamp}_{safe}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"<!-- To: {to} | Subject: {subject} -->\n{html}")
        return True
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, cfg["MAIL_SENDER"], to
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"]) as s:
        s.starttls()
        if cfg["MAIL_USERNAME"]:
            s.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
        s.sendmail(cfg["MAIL_SENDER"], [to], msg.as_string())
    return True


def send_gchat(text):
    """Post a message to a Google Chat webhook (if configured)."""
    url = current_app.config["GCHAT_WEBHOOK"]
    if not url:
        return False
    req = urllib.request.Request(url, data=json.dumps({"text": text}).encode(),
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10)
    return True
