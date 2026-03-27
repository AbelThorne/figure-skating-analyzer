from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import aiosmtplib
from jinja2 import Environment, FileSystemLoader

from app.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"
_jinja_env: Environment | None = None


def _get_jinja_env() -> Environment:
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))
    return _jinja_env


def is_smtp_configured() -> bool:
    return bool(SMTP_HOST)


async def send_email(to: str, subject: str, template_name: str, context: dict) -> bool:
    if not is_smtp_configured():
        logger.debug("SMTP not configured, skipping email to %s", to)
        return False

    try:
        env = _get_jinja_env()
        template = env.get_template(template_name)
        html_body = template.render(**context)

        msg = MIMEMultipart("alternative")
        msg["From"] = SMTP_FROM or SMTP_USER
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER or None,
            password=SMTP_PASSWORD or None,
            start_tls=True,
        )
        logger.info("Email sent to %s: %s", to, subject)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False
