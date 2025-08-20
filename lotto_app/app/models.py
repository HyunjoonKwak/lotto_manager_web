from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

db = SQLAlchemy()

class Draw(db.Model):
    __tablename__ = "draws"
    round = db.Column(db.Integer, primary_key=True)
    draw_date = db.Column(db.Date)
    n1 = db.Column(db.Integer)
    n2 = db.Column(db.Integer)
    n3 = db.Column(db.Integer)
    n4 = db.Column(db.Integer)
    n5 = db.Column(db.Integer)
    n6 = db.Column(db.Integer)
    bonus = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def as_dict(self):
        return {
            "round": self.round,
            "draw_date": self.draw_date.isoformat() if isinstance(self.draw_date, date) else None,
            "numbers": [self.n1, self.n2, self.n3, self.n4, self.n5, self.n6],
            "bonus": self.bonus,
        }

class Recommendation(db.Model):
    __tablename__ = "recommendations"
    id = db.Column(db.Integer, primary_key=True)
    round = db.Column(db.Integer, index=True)  # 의도한 회차(주차)
    kind = db.Column(db.String(20))            # "full"(6개) | "semi"(3개)
    numbers = db.Column(db.String(30))         # "1,5,9,10,30,42" 형태
    confidence = db.Column(db.Float)           # 0~1
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class RecScore(db.Model):
    __tablename__ = "rec_scores"
    id = db.Column(db.Integer, primary_key=True)
    round = db.Column(db.Integer, index=True)
    rec_id = db.Column(db.Integer, db.ForeignKey("recommendations.id"))
    match_count = db.Column(db.Integer)        # 맞춘 개수
    bonus_hit = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Shop(db.Model):
    __tablename__ = "shops"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    round = db.Column(db.Integer, index=True)
    rank = db.Column(db.Integer)               # 1등=1
    name = db.Column(db.String(200))
    address = db.Column(db.String(300))
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    raw_hash = db.Column(db.String(64))        # 중복 방지용 해시
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
