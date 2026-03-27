# Email + Internal Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add email notifications (SMTP) and an internal in-app notification system triggered when training reviews/incidents are created or updated with `visible_to_skater=true`.

**Architecture:** New `Notification` model for in-app notifications. New `email_service.py` for SMTP sending via `aiosmtplib`. A shared `notify_skater_users()` service creates in-app notifications and queues email jobs. Frontend gets a notification bell in the top bar with polling, plus an email preferences toggle on the profile page.

**Tech Stack:** aiosmtplib, Jinja2 (email templates), SQLAlchemy async, Litestar routes, React + TanStack Query (frontend)

---

### Task 1: Add `aiosmtplib` dependency and SMTP config

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Add aiosmtplib to requirements.txt**

Add `aiosmtplib>=2.0` after the `uvicorn` line in `backend/requirements.txt`:

```
aiosmtplib>=2.0
```

- [ ] **Step 2: Add SMTP config vars to config.py**

Add at the end of `backend/app/config.py`, before the directory creation lines:

```python
# SMTP (optional — email notifications disabled if SMTP_HOST is empty)
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "")
```

- [ ] **Step 3: Add SMTP section to .env.example**

Append to `.env.example`:

```bash

# === Email notifications (optional — disabled if SMTP_HOST is empty) ===
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=your-email@gmail.com
# SMTP_PASSWORD=your-app-password
# SMTP_FROM=noreply@yourclub.com
```

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt backend/app/config.py .env.example
git commit -m "feat: add SMTP config for email notifications"
```

---

### Task 2: Create Notification model

**Files:**
- Create: `backend/app/models/notification.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/database.py` (add migration)

- [ ] **Step 1: Write the Notification model**

Create `backend/app/models/notification.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # "review" or "incident"
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    link: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
```

- [ ] **Step 2: Register in models __init__.py**

Add to `backend/app/models/__init__.py`:

```python
from app.models.notification import Notification
```

And add `"Notification"` to the `__all__` list.

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/notification.py backend/app/models/__init__.py
git commit -m "feat: add Notification model for in-app notifications"
```

---

### Task 3: Create email service

**Files:**
- Create: `backend/app/services/email_service.py`

- [ ] **Step 1: Write the email service**

Create `backend/app/services/email_service.py`:

```python
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
    """Render a Jinja2 email template and send via SMTP. Returns True on success."""
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/email_service.py
git commit -m "feat: add async email service with Jinja2 templates"
```

---

### Task 4: Create email templates

**Files:**
- Create: `backend/app/templates/emails/base_email.html`
- Create: `backend/app/templates/emails/review_notification.html`
- Create: `backend/app/templates/emails/incident_notification.html`

- [ ] **Step 1: Create base email template**

Create `backend/app/templates/emails/base_email.html`:

```html
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body { margin: 0; padding: 0; font-family: Inter, -apple-system, sans-serif; font-size: 14px; color: #191c1e; background: #f5f5f5; }
  .container { max-width: 560px; margin: 20px auto; background: #ffffff; border-radius: 12px; overflow: hidden; }
  .header { background: #2e6385; padding: 20px 24px; }
  .header h1 { margin: 0; color: #ffffff; font-family: Manrope, sans-serif; font-size: 16px; font-weight: 700; }
  .content { padding: 24px; }
  .footer { padding: 16px 24px; font-size: 11px; color: #49454f; text-align: center; }
  .btn { display: inline-block; padding: 10px 20px; background: #2e6385; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 13px; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>{{ club_name | default("SkateLab") }}</h1>
  </div>
  <div class="content">
    {% block content %}{% endblock %}
  </div>
  <div class="footer">
    Vous recevez cet email car vous êtes inscrit sur la plateforme {{ club_name | default("SkateLab") }}.<br>
    Vous pouvez désactiver les notifications email dans votre profil.
  </div>
</div>
</body>
</html>
```

- [ ] **Step 2: Create review notification template**

Create `backend/app/templates/emails/review_notification.html`:

```html
{% extends "base_email.html" %}
{% block content %}
<h2 style="margin:0 0 16px; font-family:Manrope,sans-serif; font-size:18px; color:#191c1e;">
  Nouveau retour d'entraînement
</h2>
<p style="margin:0 0 8px; color:#49454f;">
  Un retour hebdomadaire a été publié pour <strong>{{ skater_name }}</strong> (semaine du {{ week_start }}).
</p>
<table style="width:100%; border-collapse:collapse; margin:16px 0;">
  <tr>
    <td style="padding:6px 12px; background:#e8f0f6; border-radius:6px 0 0 0; font-size:12px; color:#49454f;">Engagement</td>
    <td style="padding:6px 12px; background:#e8f0f6; text-align:right; font-family:monospace; font-weight:700; border-radius:0 6px 0 0;">{{ engagement }}/5</td>
  </tr>
  <tr>
    <td style="padding:6px 12px; font-size:12px; color:#49454f;">Progression</td>
    <td style="padding:6px 12px; text-align:right; font-family:monospace; font-weight:700;">{{ progression }}/5</td>
  </tr>
  <tr>
    <td style="padding:6px 12px; background:#e8f0f6; font-size:12px; color:#49454f;">Attitude</td>
    <td style="padding:6px 12px; background:#e8f0f6; text-align:right; font-family:monospace; font-weight:700;">{{ attitude }}/5</td>
  </tr>
</table>
{% if strengths %}
<p style="margin:0 0 4px; font-size:12px; font-weight:700; color:#2e6385;">Points forts</p>
<p style="margin:0 0 12px; font-size:13px;">{{ strengths }}</p>
{% endif %}
{% if improvements %}
<p style="margin:0 0 4px; font-size:12px; font-weight:700; color:#2e6385;">Axes d'amélioration</p>
<p style="margin:0 0 12px; font-size:13px;">{{ improvements }}</p>
{% endif %}
{% if app_url %}
<p style="margin:16px 0 0;"><a href="{{ app_url }}" class="btn">Voir dans l'application</a></p>
{% endif %}
{% endblock %}
```

- [ ] **Step 3: Create incident notification template**

Create `backend/app/templates/emails/incident_notification.html`:

```html
{% extends "base_email.html" %}
{% block content %}
<h2 style="margin:0 0 16px; font-family:Manrope,sans-serif; font-size:18px; color:#191c1e;">
  Nouvel incident signalé
</h2>
<p style="margin:0 0 8px; color:#49454f;">
  Un incident a été signalé pour <strong>{{ skater_name }}</strong> le {{ date }}.
</p>
<table style="width:100%; border-collapse:collapse; margin:16px 0;">
  <tr>
    <td style="padding:6px 12px; background:#e8f0f6; border-radius:6px 0 0 6px; font-size:12px; color:#49454f;">Type</td>
    <td style="padding:6px 12px; background:#e8f0f6; border-radius:0 6px 6px 0; font-weight:700;">{{ incident_type_label }}</td>
  </tr>
</table>
{% if description %}
<p style="margin:0 0 4px; font-size:12px; font-weight:700; color:#2e6385;">Description</p>
<p style="margin:0 0 12px; font-size:13px;">{{ description }}</p>
{% endif %}
{% if app_url %}
<p style="margin:16px 0 0;"><a href="{{ app_url }}" class="btn">Voir dans l'application</a></p>
{% endif %}
{% endblock %}
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/templates/emails/
git commit -m "feat: add Jinja2 email templates for review and incident notifications"
```

---

### Task 5: Create notification service (shared trigger logic)

**Files:**
- Create: `backend/app/services/notification_service.py`

- [ ] **Step 1: Write the notification service**

Create `backend/app/services/notification_service.py`:

```python
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.models.notification import Notification
from app.models.user import User
from app.models.user_skater import UserSkater
from app.models.skater import Skater
from app.services.email_service import send_email, is_smtp_configured

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

INCIDENT_TYPE_LABELS = {
    "injury": "Blessure",
    "behavior": "Comportement",
    "other": "Autre",
}


async def _get_skater_name(session: AsyncSession, skater_id: int) -> str:
    skater = await session.get(Skater, skater_id)
    if not skater:
        return "Patineur inconnu"
    if skater.first_name:
        return f"{skater.first_name} {skater.last_name}"
    return skater.last_name


async def _get_linked_skater_users(session: AsyncSession, skater_id: int) -> list[User]:
    """Return skater-role users linked to this skater who have email_notifications enabled."""
    stmt = (
        select(User)
        .join(UserSkater, UserSkater.user_id == User.id)
        .where(
            UserSkater.skater_id == skater_id,
            User.role == "skater",
            User.is_active == True,  # noqa: E712
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def notify_review(session: AsyncSession, review, app_base_url: str = "") -> None:
    """Create in-app notifications and queue emails for a visible review."""
    if not review.visible_to_skater:
        return

    skater_name = await _get_skater_name(session, review.skater_id)
    users = await _get_linked_skater_users(session, review.skater_id)

    title = f"Nouveau retour pour {skater_name}"
    message = f"Semaine du {review.week_start.isoformat()} — Engagement {review.engagement}/5, Progression {review.progression}/5, Attitude {review.attitude}/5"
    link = f"/patineurs/{review.skater_id}/analyse"

    for user in users:
        # In-app notification (always)
        notif = Notification(
            user_id=user.id,
            type="review",
            title=title,
            message=message,
            link=link,
        )
        session.add(notif)

        # Email (if enabled and SMTP configured)
        if user.email_notifications and is_smtp_configured():
            app_url = f"{app_base_url}{link}" if app_base_url else ""
            # Get club name for email template
            from app.models.app_settings import AppSettings
            settings = (await session.execute(select(AppSettings).limit(1))).scalar_one_or_none()
            club_name = settings.club_name if settings else "SkateLab"

            await send_email(
                to=user.email,
                subject=f"Nouveau retour d'entraînement pour {skater_name}",
                template_name="review_notification.html",
                context={
                    "club_name": club_name,
                    "skater_name": skater_name,
                    "week_start": review.week_start.strftime("%d/%m/%Y"),
                    "engagement": review.engagement,
                    "progression": review.progression,
                    "attitude": review.attitude,
                    "strengths": review.strengths or "",
                    "improvements": review.improvements or "",
                    "app_url": app_url,
                },
            )

    await session.flush()


async def notify_incident(session: AsyncSession, incident, app_base_url: str = "") -> None:
    """Create in-app notifications and queue emails for a visible incident."""
    if not incident.visible_to_skater:
        return

    skater_name = await _get_skater_name(session, incident.skater_id)
    users = await _get_linked_skater_users(session, incident.skater_id)

    type_label = INCIDENT_TYPE_LABELS.get(incident.incident_type, incident.incident_type)
    title = f"Incident signalé pour {skater_name}"
    message = f"{type_label} — {incident.description[:100]}" if incident.description else type_label
    link = f"/patineurs/{incident.skater_id}/analyse"

    for user in users:
        notif = Notification(
            user_id=user.id,
            type="incident",
            title=title,
            message=message,
            link=link,
        )
        session.add(notif)

        if user.email_notifications and is_smtp_configured():
            app_url = f"{app_base_url}{link}" if app_base_url else ""
            from app.models.app_settings import AppSettings
            settings = (await session.execute(select(AppSettings).limit(1))).scalar_one_or_none()
            club_name = settings.club_name if settings else "SkateLab"

            await send_email(
                to=user.email,
                subject=f"Nouvel incident signalé pour {skater_name}",
                template_name="incident_notification.html",
                context={
                    "club_name": club_name,
                    "skater_name": skater_name,
                    "date": incident.date.strftime("%d/%m/%Y"),
                    "incident_type_label": type_label,
                    "description": incident.description or "",
                    "app_url": app_url,
                },
            )

    await session.flush()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/notification_service.py
git commit -m "feat: add notification service for review and incident events"
```

---

### Task 6: Wire notifications into training routes

**Files:**
- Modify: `backend/app/routes/training.py` (lines around `create_review`, `update_review`, `create_incident`, `update_incident`)

- [ ] **Step 1: Add notification calls to training routes**

At the top of `backend/app/routes/training.py`, add import:

```python
from app.services.notification_service import notify_review, notify_incident
```

In `create_review()` (line ~126), after the final `await session.refresh(...)` and before `return`, add:

```python
    await notify_review(session, review)
    await session.commit()
```

For the upsert branch (existing review update, line ~150), after `await session.refresh(existing)` add the same pattern — but only if visibility just became True:

```python
    if existing.visible_to_skater:
        await notify_review(session, existing)
        await session.commit()
```

In `update_review()` (line ~172), after `await session.refresh(review)` and before `return`, add:

```python
    if data.get("visible_to_skater") and review.visible_to_skater:
        await notify_review(session, review)
        await session.commit()
```

In `create_incident()` (line ~271), after `await session.refresh(incident)` and before `return`:

```python
    await notify_incident(session, incident)
    await session.commit()
```

In `update_incident()` (line ~290), after `await session.refresh(incident)` and before `return`:

```python
    if data.get("visible_to_skater") and incident.visible_to_skater:
        await notify_incident(session, incident)
        await session.commit()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routes/training.py
git commit -m "feat: trigger notifications on review/incident create and update"
```

---

### Task 7: Add notification API routes

**Files:**
- Create: `backend/app/routes/notifications.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create notification routes**

Create `backend/app/routes/notifications.py`:

```python
from __future__ import annotations

from litestar import Router, get, patch, post, Request
from litestar.di import Provide
from litestar.exceptions import NotFoundException, PermissionDeniedException
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.notification import Notification


def _notif_to_dict(n: Notification) -> dict:
    return {
        "id": n.id,
        "type": n.type,
        "title": n.title,
        "message": n.message,
        "link": n.link,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


@get("/")
async def list_notifications(
    request: Request,
    session: AsyncSession,
    unread: bool | None = None,
) -> list[dict]:
    state = request.scope.get("state", {})
    user_id = state.get("user_id")
    if not user_id:
        raise PermissionDeniedException("Not authenticated")

    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    if unread is True:
        stmt = stmt.where(Notification.is_read == False)  # noqa: E712

    result = await session.execute(stmt)
    return [_notif_to_dict(n) for n in result.scalars().all()]


@get("/count")
async def unread_count(request: Request, session: AsyncSession) -> dict:
    state = request.scope.get("state", {})
    user_id = state.get("user_id")
    if not user_id:
        raise PermissionDeniedException("Not authenticated")

    stmt = (
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
    )
    result = await session.execute(stmt)
    count = result.scalar() or 0
    return {"count": count}


@patch("/{notification_id:int}/read")
async def mark_read(notification_id: int, request: Request, session: AsyncSession) -> dict:
    state = request.scope.get("state", {})
    user_id = state.get("user_id")
    if not user_id:
        raise PermissionDeniedException("Not authenticated")

    notif = await session.get(Notification, notification_id)
    if not notif:
        raise NotFoundException("Notification not found")
    if notif.user_id != user_id:
        raise PermissionDeniedException("Not your notification")

    notif.is_read = True
    await session.commit()
    return _notif_to_dict(notif)


@post("/read-all", status_code=200)
async def mark_all_read(request: Request, session: AsyncSession) -> dict:
    state = request.scope.get("state", {})
    user_id = state.get("user_id")
    if not user_id:
        raise PermissionDeniedException("Not authenticated")

    stmt = (
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
        .values(is_read=True)
    )
    result = await session.execute(stmt)
    await session.commit()
    return {"marked": result.rowcount}


router = Router(
    path="/api/me/notifications",
    route_handlers=[list_notifications, unread_count, mark_read, mark_all_read],
    dependencies={"session": Provide(get_session)},
)
```

- [ ] **Step 2: Register router in main.py**

In `backend/app/main.py`, add import:

```python
from app.routes.notifications import router as notifications_router
```

Add `notifications_router` to the `route_handlers` list in the `Litestar(...)` constructor.

- [ ] **Step 3: Commit**

```bash
git add backend/app/routes/notifications.py backend/app/main.py
git commit -m "feat: add notification API routes (list, count, mark read)"
```

---

### Task 8: Add preferences endpoint to me routes

**Files:**
- Modify: `backend/app/routes/me.py`

- [ ] **Step 1: Add preferences endpoints**

Add imports at top of `backend/app/routes/me.py`:

```python
from litestar import patch
from app.models.user import User
```

Add new route handler:

```python
@patch("/preferences")
async def update_preferences(request: Request, session: AsyncSession, data: dict) -> dict:
    state = request.scope.get("state", {})
    user_id = state.get("user_id")
    if not user_id:
        from litestar.exceptions import PermissionDeniedException
        raise PermissionDeniedException("Not authenticated")

    user = await session.get(User, user_id)
    if "email_notifications" in data:
        user.email_notifications = bool(data["email_notifications"])
    await session.commit()
    return {"email_notifications": user.email_notifications}
```

Add `update_preferences` to the `route_handlers` list in the Router.

- [ ] **Step 2: Commit**

```bash
git add backend/app/routes/me.py
git commit -m "feat: add PATCH /api/me/preferences for email notification toggle"
```

---

### Task 9: Write backend tests

**Files:**
- Create: `backend/tests/test_notifications.py`

- [ ] **Step 1: Write notification API tests**

Create `backend/tests/test_notifications.py`:

```python
"""Tests for the notification system (in-app + email preferences)."""
import pytest
from app.models.notification import Notification
from app.models.skater import Skater
from app.models.user_skater import UserSkater
from app.models.weekly_review import WeeklyReview
from app.models.incident import Incident
from datetime import date, datetime, timezone


@pytest.mark.asyncio
async def test_unread_count_empty(client, admin_token):
    res = await client.get(
        "/api/me/notifications/count",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["count"] == 0


@pytest.mark.asyncio
async def test_list_notifications_empty(client, admin_token):
    res = await client.get(
        "/api/me/notifications/",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_create_review_creates_notification(
    client, db_session, coach_token, skater_user_with_skater
):
    """When a coach creates a visible review, the linked skater user gets a notification."""
    user, _, skater = skater_user_with_skater

    res = await client.post(
        "/api/training/reviews",
        json={
            "skater_id": skater.id,
            "week_start": "2026-03-23",
            "engagement": 4,
            "progression": 3,
            "attitude": 5,
            "strengths": "Bon travail",
            "improvements": "Sauts",
            "visible_to_skater": True,
        },
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert res.status_code == 201

    # Check notification was created for the skater user
    from sqlalchemy import select
    result = await db_session.execute(
        select(Notification).where(Notification.user_id == user.id)
    )
    notifs = result.scalars().all()
    assert len(notifs) == 1
    assert notifs[0].type == "review"
    assert "Alice Dupont" in notifs[0].title
    assert notifs[0].is_read is False


@pytest.mark.asyncio
async def test_create_review_no_notification_when_not_visible(
    client, db_session, coach_token, skater_user_with_skater
):
    user, _, skater = skater_user_with_skater

    res = await client.post(
        "/api/training/reviews",
        json={
            "skater_id": skater.id,
            "week_start": "2026-03-23",
            "engagement": 4,
            "progression": 3,
            "attitude": 5,
            "visible_to_skater": False,
        },
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert res.status_code == 201

    from sqlalchemy import select
    result = await db_session.execute(
        select(Notification).where(Notification.user_id == user.id)
    )
    assert len(result.scalars().all()) == 0


@pytest.mark.asyncio
async def test_create_incident_creates_notification(
    client, db_session, coach_token, skater_user_with_skater
):
    user, _, skater = skater_user_with_skater

    res = await client.post(
        "/api/training/incidents",
        json={
            "skater_id": skater.id,
            "date": "2026-03-25",
            "incident_type": "injury",
            "description": "Cheville tordue",
            "visible_to_skater": True,
        },
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert res.status_code == 201

    from sqlalchemy import select
    result = await db_session.execute(
        select(Notification).where(Notification.user_id == user.id)
    )
    notifs = result.scalars().all()
    assert len(notifs) == 1
    assert notifs[0].type == "incident"
    assert "Alice Dupont" in notifs[0].title


@pytest.mark.asyncio
async def test_mark_read(client, db_session, admin_user, admin_token):
    user, _ = admin_user
    notif = Notification(
        user_id=user.id,
        type="review",
        title="Test",
        message="Test message",
        link="/test",
    )
    db_session.add(notif)
    await db_session.commit()
    await db_session.refresh(notif)

    res = await client.patch(
        f"/api/me/notifications/{notif.id}/read",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["is_read"] is True


@pytest.mark.asyncio
async def test_mark_all_read(client, db_session, admin_user, admin_token):
    user, _ = admin_user
    for i in range(3):
        db_session.add(Notification(
            user_id=user.id, type="review", title=f"Test {i}", message="", link="/test"
        ))
    await db_session.commit()

    res = await client.post(
        "/api/me/notifications/read-all",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["marked"] == 3

    # Verify count is 0
    res = await client.get(
        "/api/me/notifications/count",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.json()["count"] == 0


@pytest.mark.asyncio
async def test_update_preferences(client, admin_token):
    res = await client.patch(
        "/api/me/preferences",
        json={"email_notifications": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["email_notifications"] is False

    res = await client.patch(
        "/api/me/preferences",
        json={"email_notifications": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.json()["email_notifications"] is True
```

- [ ] **Step 2: Run tests**

```bash
cd backend && uv run pytest tests/test_notifications.py -v
```

Expected: All tests PASS.

- [ ] **Step 3: Run full test suite to check for regressions**

```bash
cd backend && uv run pytest -v
```

Expected: All existing tests still PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_notifications.py
git commit -m "test: add notification system tests"
```

---

### Task 10: Add frontend notification types and API functions

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add notification types**

Add after the `TimelineEntry` type (around line 483) in `frontend/src/api/client.ts`:

```typescript
export interface AppNotification {
  id: number;
  type: "review" | "incident";
  title: string;
  message: string;
  link: string;
  is_read: boolean;
  created_at: string | null;
}
```

- [ ] **Step 2: Add API functions**

Add to the `api.me` object in `frontend/src/api/client.ts`:

```typescript
  me: {
    skaters: (): Promise<MySkater[]> => request<MySkater[]>("/me/skaters"),
    notifications: {
      list: (unread?: boolean) => {
        const qs = unread !== undefined ? `?unread=${unread}` : "";
        return request<AppNotification[]>(`/me/notifications/${qs}`);
      },
      count: () => request<{ count: number }>("/me/notifications/count"),
      markRead: (id: number) =>
        request<AppNotification>(`/me/notifications/${id}/read`, { method: "PATCH" }),
      markAllRead: () =>
        request<{ marked: number }>("/me/notifications/read-all", { method: "POST" }),
    },
    updatePreferences: (data: { email_notifications: boolean }) =>
      request<{ email_notifications: boolean }>("/me/preferences", {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
  },
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add notification API types and functions to frontend client"
```

---

### Task 11: Create NotificationBell component

**Files:**
- Create: `frontend/src/components/NotificationBell.tsx`

- [ ] **Step 1: Write the notification bell component**

Create `frontend/src/components/NotificationBell.tsx`:

```tsx
import { useState, useRef, useEffect } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api, AppNotification } from "../api/client";

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: countData } = useQuery({
    queryKey: ["notifications", "count"],
    queryFn: api.me.notifications.count,
    refetchInterval: 60_000,
  });

  const { data: notifications } = useQuery({
    queryKey: ["notifications", "list"],
    queryFn: () => api.me.notifications.list(),
    enabled: open,
  });

  const markRead = useMutation({
    mutationFn: (id: number) => api.me.notifications.markRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const markAllRead = useMutation({
    mutationFn: () => api.me.notifications.markAllRead(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const count = countData?.count ?? 0;

  function handleClick(notif: AppNotification) {
    if (!notif.is_read) markRead.mutate(notif.id);
    setOpen(false);
    navigate(notif.link);
  }

  return (
    <div className="relative" ref={panelRef}>
      <button
        onClick={() => setOpen(!open)}
        className="relative text-on-surface-variant hover:text-on-surface transition-colors"
        aria-label="Notifications"
      >
        <span className="material-symbols-outlined text-2xl">notifications</span>
        {count > 0 && (
          <span className="absolute -top-1 -right-1 bg-error text-on-primary text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center">
            {count > 99 ? "99+" : count}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 bg-surface-container-lowest rounded-xl shadow-lg z-50 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3">
            <h3 className="font-headline font-bold text-sm text-on-surface">Notifications</h3>
            {count > 0 && (
              <button
                onClick={() => markAllRead.mutate()}
                className="text-xs text-primary hover:underline"
              >
                Tout marquer comme lu
              </button>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto">
            {!notifications || notifications.length === 0 ? (
              <p className="px-4 py-6 text-sm text-on-surface-variant text-center">
                Aucune notification
              </p>
            ) : (
              notifications.map((n) => (
                <button
                  key={n.id}
                  onClick={() => handleClick(n)}
                  className={`w-full text-left px-4 py-3 hover:bg-surface-container transition-colors flex gap-3 items-start ${
                    !n.is_read ? "bg-primary/5" : ""
                  }`}
                >
                  <span className="material-symbols-outlined text-lg mt-0.5 shrink-0 text-primary">
                    {n.type === "review" ? "rate_review" : "warning"}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className={`text-sm truncate ${!n.is_read ? "font-bold text-on-surface" : "text-on-surface-variant"}`}>
                      {n.title}
                    </p>
                    <p className="text-xs text-on-surface-variant truncate mt-0.5">
                      {n.message}
                    </p>
                    {n.created_at && (
                      <p className="text-[10px] text-on-surface-variant mt-1">
                        {new Date(n.created_at).toLocaleDateString("fr-FR", {
                          day: "numeric",
                          month: "short",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </p>
                    )}
                  </div>
                  {!n.is_read && (
                    <span className="w-2 h-2 rounded-full bg-primary shrink-0 mt-2" />
                  )}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/NotificationBell.tsx
git commit -m "feat: add NotificationBell component with dropdown and polling"
```

---

### Task 12: Add NotificationBell to the top bar

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add bell to the header**

Import at top of `frontend/src/App.tsx`:

```typescript
import NotificationBell from "./components/NotificationBell";
```

In the `<header>` element (around line 242), add `NotificationBell` before the closing `</header>`, making the header a flex row with the bell pushed to the right:

Change the header from:
```tsx
<header className="sticky top-0 bg-surface/70 backdrop-blur-xl z-30 shadow-sm flex items-center gap-3 px-4 lg:px-8 py-4">
  <button ...>...</button>
  <h1 ...>{pageTitle}</h1>
</header>
```

To:
```tsx
<header className="sticky top-0 bg-surface/70 backdrop-blur-xl z-30 shadow-sm flex items-center gap-3 px-4 lg:px-8 py-4">
  <button ...>...</button>
  <h1 className="font-headline font-bold text-on-surface text-xl truncate flex-1">{pageTitle}</h1>
  <NotificationBell />
</header>
```

Note: add `flex-1` to the h1 to push the bell to the right.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: add notification bell to top bar"
```

---

### Task 13: Add email preferences toggle to ProfilePage

**Files:**
- Modify: `frontend/src/pages/ProfilePage.tsx`

- [ ] **Step 1: Add email notification toggle**

In `frontend/src/pages/ProfilePage.tsx`, add imports:

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
```

Inside the `ProfilePage` component, after the existing state declarations, add:

```typescript
const queryClient = useQueryClient();

const { data: preferences } = useQuery({
  queryKey: ["me", "preferences"],
  queryFn: () => api.me.updatePreferences({ email_notifications: true }), // GET via PATCH is hacky, see step below
});
```

Actually, since there's no GET endpoint for preferences, we'll use a simple state initialized from the first PATCH response. A simpler approach: add a local state toggle that calls the API:

```typescript
const [emailNotif, setEmailNotif] = useState(true);
const [emailNotifLoading, setEmailNotifLoading] = useState(false);

async function toggleEmailNotif() {
  setEmailNotifLoading(true);
  try {
    const res = await api.me.updatePreferences({ email_notifications: !emailNotif });
    setEmailNotif(res.email_notifications);
  } catch {
    // revert on error
  } finally {
    setEmailNotifLoading(false);
  }
}
```

Add a new card section after the password change card:

```tsx
<div className="bg-surface-container-lowest rounded-xl shadow-sm p-6 max-w-md mt-6">
  <h2 className="font-headline font-bold text-on-surface text-sm mb-4">
    Préférences
  </h2>
  <div className="flex items-center justify-between">
    <div>
      <p className="text-sm text-on-surface">Notifications par email</p>
      <p className="text-xs text-on-surface-variant mt-0.5">
        Recevoir un email lors de nouveaux retours ou incidents
      </p>
    </div>
    <button
      onClick={toggleEmailNotif}
      disabled={emailNotifLoading}
      className={`relative w-11 h-6 rounded-full transition-colors ${
        emailNotif ? "bg-primary" : "bg-outline-variant"
      }`}
      aria-label="Activer les notifications email"
    >
      <span
        className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
          emailNotif ? "translate-x-5" : ""
        }`}
      />
    </button>
  </div>
</div>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/ProfilePage.tsx
git commit -m "feat: add email notification toggle to profile page"
```

---

### Task 14: Final integration test

- [ ] **Step 1: Run full backend test suite**

```bash
cd backend && uv run pytest -v
```

Expected: All tests PASS including new notification tests.

- [ ] **Step 2: Verify frontend builds**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete email + in-app notification system"
```
