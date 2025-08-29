from __future__ import annotations

from typing import Optional

from flask import Flask

from ..extensions import db
from ..models import Draw, WinningShop
from .lotto_fetcher import fetch_draw, fetch_winning_shops, NUMBERS_URL, DEFAULT_HEADERS, DEFAULT_TIMEOUT
import requests


def perform_update(round_no: int) -> dict:
    """Update both draw data and winning shops for a round.

    Handles draw and shops independently - if draw exists, only updates missing shops.
    """
    draw_updated = False
    shops_updated = False

    # Check if draw already exists
    existing_draw = Draw.query.filter_by(round=round_no).first()

    if not existing_draw:
        # Fetch and save draw data
        data = fetch_draw(round_no)
        numbers = ",".join(str(n) for n in data["numbers"])
        draw = Draw(
            round=round_no,
            draw_date=data["draw_date"],
            numbers=numbers,
            bonus=data["bonus"]
        )
        db.session.add(draw)
        db.session.commit()
        draw_updated = True

    # Check if shops exist for this round
    existing_shops_count = WinningShop.query.filter_by(round=round_no).count()

    if existing_shops_count == 0:
        # Fetch and save winning shops
        shops = fetch_winning_shops(round_no)
        if shops:
            # Clear any existing shops first (safety measure)
            WinningShop.query.filter_by(round=round_no).delete()

            # Add new shops
            for s in shops:
                db.session.add(
                    WinningShop(
                        round=round_no,
                        rank=s["rank"],
                        sequence=s.get("sequence"),
                        name=s["name"],
                        method=s.get("method"),
                        address=s.get("address"),
                        winners_count=s.get("winners_count"),
                    )
                )
            db.session.commit()
            shops_updated = True

    # Determine status
    if draw_updated and shops_updated:
        status = "updated"
    elif draw_updated or shops_updated:
        status = "partial"
    else:
        status = "skipped"

    return {
        "round": round_no,
        "status": status,
        "draw_updated": draw_updated,
        "shops_updated": shops_updated,
        "shops_count": WinningShop.query.filter_by(round=round_no).count()
    }


def update_range(start_round: int, end_round: int) -> dict:
    """Update a range of rounds, handling draws and shops independently."""
    results: list[dict] = []
    for r in range(start_round, end_round + 1):
        results.append(perform_update(r))

    # Count different statuses
    updated = sum(1 for x in results if x["status"] == "updated")
    partial = sum(1 for x in results if x["status"] == "partial")
    skipped = sum(1 for x in results if x["status"] == "skipped")

    # Count actual updates
    draws_updated = sum(1 for x in results if x["draw_updated"])
    shops_updated = sum(1 for x in results if x["shops_updated"])

    return {
        "range": [start_round, end_round],
        "total_rounds": len(results),
        "updated": updated,
        "partial": partial,
        "skipped": skipped,
        "draws_updated": draws_updated,
        "shops_updated": shops_updated
    }


def get_latest_round() -> Optional[int]:
    """Find the latest available round by probing the official API.

    Strategy: exponential search to find an upper bound, then binary search for last success.
    Returns None if no rounds are available.
    """
    def exists(r: int) -> bool:
        try:
            url = NUMBERS_URL.format(round=r)
            resp = requests.get(url, timeout=DEFAULT_TIMEOUT, headers=DEFAULT_HEADERS)
            resp.raise_for_status()
            data = resp.json()
            return data.get("returnValue") == "success"
        except Exception:
            return False

    # If round 1 doesn't exist, nothing to do
    if not exists(1):
        return None

    # Exponential search to find upper bound where it fails
    lo = 1
    hi = 2
    while exists(hi):
        lo = hi
        hi *= 2

    # Binary search between lo (success) and hi (fail)
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if exists(mid):
            lo = mid
        else:
            hi = mid

    return lo
