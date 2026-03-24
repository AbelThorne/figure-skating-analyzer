from __future__ import annotations

import base64
from pathlib import Path

from litestar import Router, get
from litestar.di import Provide
from litestar.exceptions import NotFoundException
from litestar.response import Response
from sqlalchemy.ext.asyncio import AsyncSession
from jinja2 import Environment, FileSystemLoader

from app.database import get_session
from app.services.report_data import get_skater_report_data, get_club_report_data

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))


def _load_logo_base64(logo_path: str | None) -> str | None:
    if not logo_path:
        return None
    p = Path(logo_path)
    if not p.is_file():
        return None
    return base64.b64encode(p.read_bytes()).decode()


@get("/skater/{skater_id:int}/pdf")
async def skater_report_pdf(
    skater_id: int,
    season: str,
    session: AsyncSession,
) -> Response:
    import weasyprint

    data = await get_skater_report_data(skater_id, season, session)
    if not data.results:
        raise NotFoundException(detail="Aucun résultat pour cette saison")

    logo_b64 = _load_logo_base64(None)
    template = _jinja_env.get_template("reports/skater_season.html")
    html = template.render(data=data, logo_base64=logo_b64)
    pdf_bytes = weasyprint.HTML(string=html).write_pdf()

    safe_name = data.skater_name.replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="rapport-{safe_name}-{season}.pdf"'
        },
    )


@get("/club/pdf")
async def club_report_pdf(
    season: str,
    session: AsyncSession,
) -> Response:
    import weasyprint

    data = await get_club_report_data(season, session)
    if not data.skaters_summary:
        raise NotFoundException(detail="Aucun résultat pour cette saison")

    logo_b64 = _load_logo_base64(data.club_logo_path)
    template = _jinja_env.get_template("reports/club_season.html")
    html = template.render(data=data, logo_base64=logo_b64)
    pdf_bytes = weasyprint.HTML(string=html).write_pdf()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="rapport-club-{season}.pdf"'
        },
    )


router = Router(
    path="/api/reports",
    route_handlers=[skater_report_pdf, club_report_pdf],
    dependencies={"session": Provide(get_session)},
)
