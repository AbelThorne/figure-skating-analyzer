from app.models.competition import Competition
from app.models.skater import Skater
from app.models.score import Score
from app.models.category_result import CategoryResult
from app.models.user import User
from app.models.user_skater import UserSkater
from app.models.allowed_domain import AllowedDomain
from app.models.app_settings import AppSettings
from app.models.skater_alias import SkaterAlias
from app.models.weekly_review import WeeklyReview
from app.models.incident import Incident
from app.models.challenge import Challenge

__all__ = [
    "Competition",
    "Skater",
    "Score",
    "CategoryResult",
    "User",
    "UserSkater",
    "AllowedDomain",
    "AppSettings",
    "SkaterAlias",
    "WeeklyReview",
    "Incident",
    "Challenge",
]
