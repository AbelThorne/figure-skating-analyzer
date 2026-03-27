from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import TYPE_CHECKING

import aiosmtplib
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select

from app.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"
_jinja_env: Environment | None = None


def _get_jinja_env() -> Environment:
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))
    return _jinja_env


def is_smtp_configured() -> bool:
    """Check env-var level SMTP config (quick sync check)."""
    return bool(SMTP_HOST)


async def get_smtp_config(session: AsyncSession) -> dict | None:
    """Return SMTP config from DB settings, falling back to env vars.

    Returns None if no SMTP is configured at all.
    """
    from app.models.app_settings import AppSettings

    settings = (await session.execute(select(AppSettings).limit(1))).scalar_one_or_none()

    # DB settings take priority if smtp_host is set
    if settings and settings.smtp_host:
        from_addr = settings.smtp_from or settings.smtp_user or ""
        if settings.smtp_from_name and from_addr:
            from_addr = f"{settings.smtp_from_name} <{from_addr}>"
        return {
            "host": settings.smtp_host,
            "port": settings.smtp_port or 587,
            "user": settings.smtp_user or "",
            "password": settings.smtp_password or "",
            "from_addr": from_addr,
        }

    # Fall back to env vars
    if SMTP_HOST:
        return {
            "host": SMTP_HOST,
            "port": SMTP_PORT,
            "user": SMTP_USER,
            "password": SMTP_PASSWORD,
            "from_addr": SMTP_FROM or SMTP_USER,
        }

    return None


async def send_email(
    to: str,
    subject: str,
    template_name: str,
    context: dict,
    smtp_config: dict | None = None,
) -> bool:
    """Send an email. If smtp_config is provided, use it; otherwise use env vars."""
    cfg = smtp_config
    if cfg is None:
        # Legacy path: use env vars directly
        if not SMTP_HOST:
            logger.debug("SMTP not configured, skipping email to %s", to)
            return False
        cfg = {
            "host": SMTP_HOST,
            "port": SMTP_PORT,
            "user": SMTP_USER,
            "password": SMTP_PASSWORD,
            "from_addr": SMTP_FROM or SMTP_USER,
        }

    try:
        env = _get_jinja_env()
        template = env.get_template(template_name)
        html_body = template.render(**context)

        msg = MIMEMultipart("alternative")
        msg["From"] = cfg["from_addr"]
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        await aiosmtplib.send(
            msg,
            hostname=cfg["host"],
            port=cfg["port"],
            username=cfg["user"] or None,
            password=cfg["password"] or None,
            start_tls=True,
        )
        logger.info("Email sent to %s: %s", to, subject)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False


async def send_test_email(smtp_config: dict, to: str) -> bool:
    """Send a test email using the provided SMTP config."""
    return await send_email(
        to=to,
        subject="Test SMTP — SkateLab",
        template_name="test_email.html",
        context={"to_email": to},
        smtp_config=smtp_config,
    )
