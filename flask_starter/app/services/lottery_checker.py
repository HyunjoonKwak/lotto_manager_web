from typing import List, Tuple, Optional
from ..models import Draw, Purchase
from ..extensions import db


def check_winning_result(purchase_numbers: List[int], draw: Draw) -> Tuple[Optional[int], int, bool, Optional[int]]:
    """
    구매 번호와 당첨 번호를 비교하여 당첨 결과 확인

    Returns:
        (winning_rank, matched_count, bonus_matched, prize_amount)
        winning_rank: 1~5등, None=낙첨
        matched_count: 맞춘 번호 개수
        bonus_matched: 보너스 번호 일치 여부
        prize_amount: 당첨금 (실제 배당금은 API에서 가져와야 하므로 예상값)
    """
    winning_numbers = draw.numbers_list()
    bonus_number = draw.bonus

    # 메인 번호 매칭 개수
    matched_count = len(set(purchase_numbers) & set(winning_numbers))

    # 보너스 번호 매칭 여부
    bonus_matched = bonus_number in purchase_numbers

    # 당첨 등수 결정
    winning_rank = None
    prize_amount = None

    if matched_count == 6:
        winning_rank = 1
        prize_amount = 2000000000  # 20억 (예상값)
    elif matched_count == 5 and bonus_matched:
        winning_rank = 2
        prize_amount = 100000000   # 1억 (예상값)
    elif matched_count == 5:
        winning_rank = 3
        prize_amount = 1500000     # 150만원 (예상값)
    elif matched_count == 4:
        winning_rank = 4
        prize_amount = 50000       # 5만원
    elif matched_count == 3:
        winning_rank = 5
        prize_amount = 5000        # 5천원

    return winning_rank, matched_count, bonus_matched, prize_amount


def update_purchase_results(purchase_round: int) -> int:
    """
    특정 회차의 모든 구매 기록에 대해 당첨 결과 업데이트

    Returns:
        업데이트된 구매 기록 수
    """
    # 해당 회차의 당첨 번호 조회
    draw = Draw.query.filter_by(round=purchase_round).first()
    if not draw:
        return 0

    # 해당 회차의 미확인 구매 기록들 조회
    purchases = Purchase.query.filter_by(
        purchase_round=purchase_round,
        result_checked=False
    ).all()

    updated_count = 0
    for purchase in purchases:
        # 당첨 결과 확인
        winning_rank, matched_count, bonus_matched, prize_amount = check_winning_result(
            purchase.numbers_list(), draw
        )

        # 결과 업데이트
        purchase.result_checked = True
        purchase.winning_rank = winning_rank
        purchase.matched_count = matched_count
        purchase.bonus_matched = bonus_matched
        purchase.prize_amount = prize_amount

        updated_count += 1

    db.session.commit()
    return updated_count


def get_purchase_statistics() -> dict:
    """구매 및 당첨 통계 조회"""
    total_purchases = Purchase.query.count()
    checked_purchases = Purchase.query.filter_by(result_checked=True).count()
    unchecked_purchases = total_purchases - checked_purchases

    # 등수별 당첨 통계
    winning_stats = {}
    for rank in range(1, 6):
        count = Purchase.query.filter_by(winning_rank=rank).count()
        winning_stats[f"rank_{rank}"] = count

    # 낙첨 수
    losing_count = Purchase.query.filter(
        Purchase.result_checked == True,
        Purchase.winning_rank.is_(None)
    ).count()

    # 총 당첨금
    total_prize = db.session.query(db.func.sum(Purchase.prize_amount)).filter(
        Purchase.prize_amount.isnot(None)
    ).scalar() or 0

    return {
        "total_purchases": total_purchases,
        "checked_purchases": checked_purchases,
        "unchecked_purchases": unchecked_purchases,
        "winning_stats": winning_stats,
        "losing_count": losing_count,
        "total_prize": total_prize
    }


def get_recent_purchases_with_results(limit: int = 20) -> List[Purchase]:
    """최근 구매 기록을 당첨 결과와 함께 조회"""
    return Purchase.query.order_by(Purchase.purchase_date.desc()).limit(limit).all()


def check_all_pending_results() -> dict:
    """모든 미확인 결과를 확인하고 업데이트"""
    # 결과가 확인되지 않은 구매 기록들의 회차 목록
    pending_rounds = db.session.query(Purchase.purchase_round).filter_by(
        result_checked=False
    ).distinct().all()

    total_updated = 0
    updated_rounds = []

    for (round_no,) in pending_rounds:
        # 해당 회차의 당첨 번호가 있는지 확인
        if Draw.query.filter_by(round=round_no).first():
            updated = update_purchase_results(round_no)
            if updated > 0:
                total_updated += updated
                updated_rounds.append(round_no)

    return {
        "total_updated": total_updated,
        "updated_rounds": updated_rounds
    }
