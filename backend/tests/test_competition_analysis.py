"""Tests for competition club analysis service."""

import pytest
from app.services.competition_analysis import compute_club_challenge_points


def test_single_skater_in_category():
    """1 skater: gets 1 base + 3 podium = 4."""
    result = compute_club_challenge_points(rank=1, total_in_category=1)
    assert result == {"base": 1, "podium": 3, "total": 4}


def test_two_skaters():
    """2 skaters: rank 1 gets 2+3=5, rank 2 gets 1+2=3."""
    r1 = compute_club_challenge_points(rank=1, total_in_category=2)
    assert r1 == {"base": 2, "podium": 3, "total": 5}
    r2 = compute_club_challenge_points(rank=2, total_in_category=2)
    assert r2 == {"base": 1, "podium": 2, "total": 3}


def test_four_skaters():
    """4 skaters: rank 1=7, rank 2=5, rank 3=3, rank 4=1."""
    assert compute_club_challenge_points(1, 4) == {"base": 4, "podium": 3, "total": 7}
    assert compute_club_challenge_points(2, 4) == {"base": 3, "podium": 2, "total": 5}
    assert compute_club_challenge_points(3, 4) == {"base": 2, "podium": 1, "total": 3}
    assert compute_club_challenge_points(4, 4) == {"base": 1, "podium": 0, "total": 1}


def test_ten_skaters_cap():
    """10 skaters: rank 1 gets 10+3=13, rank 10 gets 1."""
    assert compute_club_challenge_points(1, 10) == {"base": 10, "podium": 3, "total": 13}
    assert compute_club_challenge_points(10, 10) == {"base": 1, "podium": 0, "total": 1}


def test_eleven_skaters_capped_at_ten():
    """11 skaters: rank 1 still gets 10+3=13, ranks 10 and 11 both get 1."""
    assert compute_club_challenge_points(1, 11) == {"base": 10, "podium": 3, "total": 13}
    assert compute_club_challenge_points(10, 11) == {"base": 1, "podium": 0, "total": 1}
    assert compute_club_challenge_points(11, 11) == {"base": 1, "podium": 0, "total": 1}


def test_fifteen_skaters_beyond_tenth():
    """15 skaters: ranks 11-15 all get 1 base, 0 podium."""
    for rank in range(11, 16):
        assert compute_club_challenge_points(rank, 15) == {"base": 1, "podium": 0, "total": 1}
