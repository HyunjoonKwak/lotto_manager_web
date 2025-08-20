from app.models import db, Draw, Recommendation, RecScore

def _match_count(win_nums, cand):
    hit = len(set(win_nums) & set(cand))
    return hit

def score_recommendations_for_round(round_no: int):
    draw = Draw.query.get(round_no)
    if not draw:
        return {"scored": 0, "message": "draw not found"}

    win = [draw.n1, draw.n2, draw.n3, draw.n4, draw.n5, draw.n6]
    bonus = draw.bonus

    recs = Recommendation.query.all()  # 과거 전체와 비교
    made = 0
    for r in recs:
        nums = list(map(int, r.numbers.split(",")))
        mc = _match_count(win, nums)
        bonus_hit = (bonus in nums)
        rs = RecScore(round=round_no, rec_id=r.id, match_count=mc, bonus_hit=bonus_hit)
        db.session.add(rs)
        made += 1
    db.session.commit()
    return {"scored": made, "round": round_no}
