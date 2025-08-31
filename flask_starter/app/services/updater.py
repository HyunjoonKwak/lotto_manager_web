import requests
import time
from typing import Dict, List, Optional

from flask import Flask

from ..extensions import db
from ..models import Draw, WinningShop
from .lotto_fetcher import fetch_draw, fetch_winning_shops, NUMBERS_URL, DEFAULT_HEADERS, DEFAULT_TIMEOUT


def perform_update(round_no: int, data_type: str = 'both') -> dict:
    """Update draw data and/or winning shops for a round based on data_type.

    Args:
        round_no: Round number to update
        data_type: 'both', 'numbers', or 'shops'

    Handles draw and shops independently - if draw exists, only updates missing data.
    """
    draw_updated = False
    shops_updated = False

    # Update draw data if requested
    if data_type in ['both', 'numbers']:
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

    # Update shops data if requested
    if data_type in ['both', 'shops']:
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


def update_range(start_round: int, end_round: int, data_type: str = 'both') -> dict:
    """Update a range of rounds, handling draws and shops based on data_type."""
    results: list[dict] = []
    for r in range(start_round, end_round + 1):
        results.append(perform_update(r, data_type))

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


def find_missing_rounds() -> List[int]:
    """Find rounds that are missing from the database between 1 and the latest available round."""
    latest_round = get_latest_round()
    if not latest_round:
        return []

    # Get all existing rounds from database
    existing_rounds = set(
        row[0] for row in db.session.query(Draw.round).filter(Draw.round <= latest_round).all()
    )

    # Find missing rounds
    all_rounds = set(range(1, latest_round + 1))
    missing_rounds = sorted(all_rounds - existing_rounds)

    return missing_rounds


def update_missing_rounds() -> dict:
    """Update all missing rounds between 1 and the latest available round."""
    missing = find_missing_rounds()
    if not missing:
        return {
            "status": "up_to_date",
            "total_missing": 0,
            "updated": 0,
            "failed": 0
        }

    updated = 0
    failed = 0

    for round_no in missing:
        try:
            result = perform_update(round_no)
            if result["status"] in ["updated", "partial"]:
                updated += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    return {
        "status": "completed",
        "total_missing": len(missing),
        "updated": updated,
        "failed": failed,
        "missing_rounds": missing[:10] if len(missing) > 10 else missing
    }


def update_to_latest() -> dict:
    """Update from current max round + 1 to the latest available round."""
    latest_round = get_latest_round()
    if not latest_round:
        return {"status": "error", "message": "Cannot detect latest round"}

    # Find current max round in database
    current_max = db.session.query(db.func.max(Draw.round)).scalar() or 0
    start_round = current_max + 1

    if start_round > latest_round:
        return {
            "status": "up_to_date",
            "current_max": current_max,
            "latest_available": latest_round
        }

    return update_range(start_round, latest_round)


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
