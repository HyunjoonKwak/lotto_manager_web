import json
import uuid
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any, Optional
from flask import session

from ..models import RecommendationSet
from ..extensions import db
from .recommender import auto_recommend
from .analyzer import get_recommendation_reasons


def get_or_create_session_id() -> str:
    """세션 ID를 가져오거나 새로 생성"""
    if 'recommendation_session_id' not in session:
        session['recommendation_session_id'] = str(uuid.uuid4())
    return session['recommendation_session_id']


def get_stored_recommendations() -> Optional[Tuple[List[List[int]], List[List[str]]]]:
    """저장된 추천번호와 이유를 가져옴"""
    session_id = get_or_create_session_id()

    # 24시간 이내의 추천번호만 유효하다고 가정
    cutoff_time = datetime.utcnow() - timedelta(hours=24)

    recommendation_set = RecommendationSet.query.filter(
        RecommendationSet.session_id == session_id,
        RecommendationSet.created_at > cutoff_time
    ).order_by(RecommendationSet.created_at.desc()).first()

    if recommendation_set:
        try:
            numbers_data = json.loads(recommendation_set.numbers_set)
            reasons_data = json.loads(recommendation_set.reasons_set) if recommendation_set.reasons_set else []
            return numbers_data, reasons_data
        except (json.JSONDecodeError, TypeError):
            # 데이터가 손상된 경우 삭제
            db.session.delete(recommendation_set)
            db.session.commit()

    return None


def store_recommendations(numbers_sets: List[List[int]], reasons_sets: List[List[str]]):
    """추천번호와 이유를 저장"""
    session_id = get_or_create_session_id()

    # 기존 추천번호 삭제 (세션별로 하나만 유지)
    old_recommendations = RecommendationSet.query.filter_by(session_id=session_id).all()
    for old_rec in old_recommendations:
        db.session.delete(old_rec)

    # 새 추천번호 저장
    new_recommendation = RecommendationSet(
        session_id=session_id,
        numbers_set=json.dumps(numbers_sets),
        reasons_set=json.dumps(reasons_sets)
    )

    db.session.add(new_recommendation)
    db.session.commit()


def get_persistent_recommendations(draws: List) -> Tuple[List[List[int]], List[List[str]]]:
    """지속적인 추천번호를 가져오거나 새로 생성"""
    stored_data = get_stored_recommendations()

    if stored_data is not None:
        # 저장된 추천번호가 있으면 반환
        return stored_data

    # 저장된 추천번호가 없으면 새로 생성
    history = [d.numbers_list() for d in draws]
    auto_recs = auto_recommend(history, count=5)

    # Generate reasons for recommendations
    recommendation_reasons = []
    for rec in auto_recs:
        recommendation_reasons.append(get_recommendation_reasons(rec, limit=None))

    # 새로 생성한 추천번호 저장
    store_recommendations(auto_recs, recommendation_reasons)

    return auto_recs, recommendation_reasons


def refresh_recommendations(draws: List) -> Tuple[List[List[int]], List[List[str]]]:
    """강제로 새로운 추천번호 생성"""
    history = [d.numbers_list() for d in draws]
    auto_recs = auto_recommend(history, count=5)

    # Generate reasons for recommendations
    recommendation_reasons = []
    for rec in auto_recs:
        recommendation_reasons.append(get_recommendation_reasons(rec, limit=None))

    store_recommendations(auto_recs, recommendation_reasons)
    return auto_recs, recommendation_reasons


def cleanup_old_recommendations():
    """오래된 추천번호 데이터 정리 (7일 이상 된 것)"""
    cutoff_time = datetime.utcnow() - timedelta(days=7)
    old_recommendations = RecommendationSet.query.filter(
        RecommendationSet.created_at < cutoff_time
    ).all()

    for old_rec in old_recommendations:
        db.session.delete(old_rec)

    db.session.commit()
    return len(old_recommendations)
