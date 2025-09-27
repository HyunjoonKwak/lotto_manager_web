from datetime import datetime
from typing import List
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

from .extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)

    # Login attempt tracking
    failed_login_attempts = db.Column(db.Integer, nullable=False, default=0)
    last_failed_login = db.Column(db.DateTime, nullable=True)
    account_locked_until = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_account_locked(self):
        """Check if account is currently locked"""
        if self.account_locked_until is None:
            return False
        return datetime.utcnow() < self.account_locked_until

    def increment_failed_login(self):
        """Increment failed login attempts and lock account if necessary"""
        self.failed_login_attempts += 1
        self.last_failed_login = datetime.utcnow()

        # Lock account for 15 minutes after 5 failed attempts
        if self.failed_login_attempts >= 5:
            from datetime import timedelta
            self.account_locked_until = datetime.utcnow() + timedelta(minutes=15)

    def reset_failed_login(self):
        """Reset failed login attempts on successful login"""
        self.failed_login_attempts = 0
        self.last_failed_login = None
        self.account_locked_until = None

    def has_admin_role(self):
        """Check if user has admin privileges"""
        return self.is_admin and self.is_active

    def __repr__(self):
        return f'<User {self.username}>'


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
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)  # 구매자 ID
    purchase_round = db.Column(db.Integer, nullable=False, index=True)  # 구매한 회차
    numbers = db.Column(db.String(50), nullable=False)  # e.g. "1,2,3,4,5,6"
    purchase_method = db.Column(db.String(20), nullable=True)  # 자동/수동/반자동
    purchase_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # QR/OCR 수집 관련 필드
    recognition_method = db.Column(db.String(10), nullable=True)  # 'QR', 'OCR'
    confidence_score = db.Column(db.Float, nullable=True)  # 인식 신뢰도 (0-100)
    source = db.Column(db.String(50), nullable=True)  # 'local_collector', 'manual'

    # User 관계 설정
    user = db.relationship('User', backref=db.backref('purchases', lazy=True))

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
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)  # 사용자별 추천번호 관리
    session_id = db.Column(db.String(100), nullable=False, index=True)  # 세션별 추천번호 관리 (하위 호환성)
    numbers_set = db.Column(db.Text, nullable=False)  # JSON 형태로 5세트 저장
    reasons_set = db.Column(db.Text, nullable=True)  # JSON 형태로 추천 이유 저장
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # User 관계 설정
    user = db.relationship('User', backref=db.backref('recommendation_sets', lazy=True))


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    token = db.Column(db.String(100), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # User 관계 설정
    user = db.relationship('User', backref=db.backref('password_reset_tokens', lazy=True))

    def is_expired(self):
        """Check if token is expired"""
        return datetime.utcnow() > self.expires_at

    def is_valid(self):
        """Check if token is valid (not used and not expired)"""
        return not self.used and not self.is_expired()
