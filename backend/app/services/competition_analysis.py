"""Competition club analysis service."""


def compute_club_challenge_points(rank: int, total_in_category: int) -> dict:
    """Compute club challenge points for a skater at a given rank.

    Base points: max(1, min(11 - rank, total - rank + 1))
    - Counts backwards from last place (total - rank + 1)
    - Capped by rank position (11 - rank gives max 10 for rank 1, max 1 for rank 10+)
    - Minimum 1 point for participation

    Podium bonus: rank 1 -> +3, rank 2 -> +2, rank 3 -> +1.
    """
    base = max(1, min(11 - rank, total_in_category - rank + 1))
    podium = {1: 3, 2: 2, 3: 1}.get(rank, 0)
    return {"base": base, "podium": podium, "total": base + podium}
