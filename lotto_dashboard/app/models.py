from .extensions import db
from datetime import datetime

class Draw(db.Model):
    __tablename__ = "draws"
    id = db.Column(db.Integer, primary_key=True)
    round = db.Column(db.Integer, unique=True, nullable=False, index=True)
    draw_date = db.Column(db.String(16), nullable=True)
    n1 = db.Column(db.Integer, nullable=False)
    n2 = db.Column(db.Integer, nullable=False)
    n3 = db.Column(db.Integer, nullable=False)
    n4 = db.Column(db.Integer, nullable=False)
    n5 = db.Column(db.Integer, nullable=False)
    n6 = db.Column(db.Integer, nullable=False)
    bonus = db.Column(db.Integer, nullable=False)
    def numbers(self):
        return [self.n1, self.n2, self.n3, self.n4, self.n5, self.n6]

class Recommendation(db.Model):
    __tablename__ = "recommendations"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    type = db.Column(db.String(10), nullable=False)  # 'full' or 'semi'
    nums = db.Column(db.String(64), nullable=False)  # "1,2,3,4,5,6" or "1,2,3"
    method = db.Column(db.String(32), nullable=True)
    note = db.Column(db.String(255), nullable=True)
    round_expected = db.Column(db.Integer, nullable=True, index=True)

class RecMatch(db.Model):
    __tablename__ = "rec_matches"
    id = db.Column(db.Integer, primary_key=True)
    draw_round = db.Column(db.Integer, index=True, nullable=False)
    recommendation_id = db.Column(db.Integer, db.ForeignKey('recommendations.id'), nullable=False)
    matched_count = db.Column(db.Integer, nullable=False)
    matched_nums = db.Column(db.String(64), nullable=False)

class Shop(db.Model):
    __tablename__ = "shops"
    id = db.Column(db.Integer, primary_key=True)
    round = db.Column(db.Integer, index=True, nullable=False)
    rank = db.Column(db.Integer, nullable=True)
    name = db.Column(db.String(128), nullable=False)
    address = db.Column(db.String(256), nullable=True)
    method = db.Column(db.String(32), nullable=True)
    lat = db.Column(db.Float, nullable=True)
    lon = db.Column(db.Float, nullable=True)
    __table_args__ = (db.UniqueConstraint('round', 'name', 'address', name='uq_shop_round_name_addr'),)
