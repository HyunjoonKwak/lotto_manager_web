import json
import uuid
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any, Optional
from flask import session

from ..models import RecommendationSet
from ..extensions import db
from .recommender import auto_recommend, enhanced_auto_recommend
from .analyzer import get_recommendation_reasons


def get_or_create_session_id() -> str:
    """세션 ID를 가져오거나 새로 생성"""
    if 'recommendation_session_id' not in session:
        session['recommendation_session_id'] = str(uuid.uuid4())
    return session['recommendation_session_id']


def get_stored_recommendations(user_id: int = None) -> Optional[Tuple[List[List[int]], List[List[str]]]]:
    """저장된 추천번호와 이유를 가져옴 (사용자별 또는 세션별)"""
    # 24시간 이내의 추천번호만 유효하다고 가정
    cutoff_time = datetime.utcnow() - timedelta(hours=24)

    if user_id:
        # 로그인한 사용자의 추천번호 조회
        recommendation_set = RecommendationSet.query.filter(
            RecommendationSet.user_id == user_id,
            RecommendationSet.created_at > cutoff_time
        ).order_by(RecommendationSet.created_at.desc()).first()
    else:
        # 세션 기반 추천번호 조회 (하위 호환성)
        session_id = get_or_create_session_id()
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


def store_recommendations(numbers_sets: List[List[int]], reasons_sets: List[List[str]], user_id: int = None):
    """추천번호와 이유를 저장 (사용자별 또는 세션별)"""

    if user_id:
        # 로그인한 사용자의 기존 추천번호 삭제
        old_recommendations = RecommendationSet.query.filter_by(user_id=user_id).all()
        for old_rec in old_recommendations:
            db.session.delete(old_rec)

        # 새 추천번호 저장 (사용자별)
        new_recommendation = RecommendationSet(
            user_id=user_id,
            session_id=get_or_create_session_id(),  # 하위 호환성
            numbers_set=json.dumps(numbers_sets),
            reasons_set=json.dumps(reasons_sets)
        )
    else:
        # 세션 기반 저장 (하위 호환성)
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


def get_persistent_recommendations(draws: List, user_id: int = None) -> Tuple[List[List[int]], List[List[str]]]:
    """지속적인 추천번호를 가져오거나 새로 생성"""
    stored_data = get_stored_recommendations(user_id)

    if stored_data is not None:
        # 저장된 추천번호가 있으면 반환
        return stored_data

    # 저장된 추천번호가 없으면 새로 생성
    try:
        history = []
        for d in draws:
            try:
                numbers = d.numbers_list()
                if numbers and len(numbers) == 6:  # 유효한 번호만 추가
                    history.append(numbers)
            except (AttributeError, ValueError, TypeError) as e:
                # 개별 draw 처리 중 오류가 있어도 계속 진행
                continue

        if not history:
            # 유효한 데이터가 없으면 기본 추천 생성
            history = [[1, 2, 3, 4, 5, 6]]  # 기본값

        auto_recs, recommendation_reasons = enhanced_auto_recommend(history, user_id=user_id, count=5)
    except Exception as e:
        # 전체 추천 생성 실패 시 기본 추천 반환
        auto_recs = [[7, 14, 21, 28, 35, 42], [3, 9, 15, 27, 33, 39], [5, 11, 17, 23, 29, 41], [8, 16, 24, 32, 36, 44], [2, 12, 18, 26, 34, 43]]
        recommendation_reasons = [
            ["균등 분포 패턴", "7의 배수 활용"],
            ["저구간 강세", "홀수 위주"],
            ["전구간 균형", "소수 활용"],
            ["짝수 기반", "연속성 고려"],
            ["중간값 기반", "균형 배치"]
        ]

    # 새로 생성한 추천번호 저장
    store_recommendations(auto_recs, recommendation_reasons, user_id)

    return auto_recs, recommendation_reasons


def refresh_recommendations(draws: List, user_id: int = None) -> Tuple[List[List[int]], List[List[str]]]:
    """강제로 새로운 추천번호 생성"""
    history = [d.numbers_list() for d in draws]
    auto_recs, recommendation_reasons = enhanced_auto_recommend(history, user_id=user_id, count=5)

    store_recommendations(auto_recs, recommendation_reasons, user_id)
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
