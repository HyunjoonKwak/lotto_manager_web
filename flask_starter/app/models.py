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
