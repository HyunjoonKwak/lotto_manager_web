from datetime import datetime
from typing import List

from .extensions import db


class Example(db.Model):
    __tablename__ = "example"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Draw(db.Model):
    __tablename__ = "draws"

    id = db.Column(db.Integer, primary_key=True)
    round = db.Column(db.Integer, unique=True, nullable=False, index=True)
    draw_date = db.Column(db.Date, nullable=True)
    numbers = db.Column(db.String(50), nullable=False)  # e.g. "1,2,3,4,5,6"
    bonus = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def numbers_list(self) -> List[int]:
        return [int(x) for x in self.numbers.split(",") if x]


class WinningShop(db.Model):
    __tablename__ = "winning_shops"

    id = db.Column(db.Integer, primary_key=True)
    round = db.Column(db.Integer, nullable=False, index=True)
    rank = db.Column(db.Integer, nullable=False)  # 1 or 2
    sequence = db.Column(db.Integer, nullable=True)  # 순번(표시 번호)
    name = db.Column(db.String(200), nullable=False)
    method = db.Column(db.String(20), nullable=True)  # 자동/수동/반자동 (2등은 없음)
    address = db.Column(db.String(400), nullable=True)
    winners_count = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Purchase(db.Model):
    __tablename__ = "purchases"

    id = db.Column(db.Integer, primary_key=True)
    purchase_round = db.Column(db.Integer, nullable=False, index=True)  # 구매한 회차
    numbers = db.Column(db.String(50), nullable=False)  # e.g. "1,2,3,4,5,6"
    purchase_method = db.Column(db.String(20), nullable=True)  # 자동/수동/반자동
    purchase_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # 당첨 결과 (추첨 후 업데이트)
    result_checked = db.Column(db.Boolean, nullable=False, default=False)
    winning_rank = db.Column(db.Integer, nullable=True)  # 1등~5등, None=낙첨
    matched_count = db.Column(db.Integer, nullable=True)  # 맞춘 번호 개수
    bonus_matched = db.Column(db.Boolean, nullable=False, default=False)  # 보너스 번호 일치 여부
    prize_amount = db.Column(db.Integer, nullable=True)  # 당첨금액 (원)

    def numbers_list(self) -> List[int]:
        return [int(x) for x in self.numbers.split(",") if x]

    def get_winning_status(self) -> str:
        if not self.result_checked:
            return "결과 대기"
        if self.winning_rank is None:
            return "낙첨"
        return f"{self.winning_rank}등 당첨"


class RecommendationSet(db.Model):
    __tablename__ = "recommendation_sets"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False, index=True)  # 세션별 추천번호 관리
    numbers_set = db.Column(db.Text, nullable=False)  # JSON 형태로 5세트 저장
    reasons_set = db.Column(db.Text, nullable=True)  # JSON 형태로 추천 이유 저장
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
