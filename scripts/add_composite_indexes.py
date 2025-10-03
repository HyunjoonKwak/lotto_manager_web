#!/usr/bin/env python3
"""
데이터베이스 성능 최적화를 위한 복합 인덱스 추가 스크립트

Phase 3.3: 성능 최적화
- Purchase 테이블에 복합 인덱스 추가
- 자주 사용되는 쿼리 패턴 최적화

실행 방법:
    python scripts/add_composite_indexes.py
"""

import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import create_app
from app.extensions import db
from sqlalchemy import text, inspect


def check_index_exists(engine, table_name, index_name):
    """인덱스가 이미 존재하는지 확인"""
    inspector = inspect(engine)
    indexes = inspector.get_indexes(table_name)
    return any(idx['name'] == index_name for idx in indexes)


def add_composite_indexes():
    """복합 인덱스 추가"""
    app = create_app()

    with app.app_context():
        engine = db.engine

        print("=" * 60)
        print("데이터베이스 성능 최적화: 복합 인덱스 추가")
        print("=" * 60)
        print()

        # 추가할 인덱스 목록
        indexes_to_add = [
            # Purchase 테이블 복합 인덱스
            {
                'table': 'purchases',
                'name': 'idx_purchases_user_status',
                'columns': ['user_id', 'status'],
                'description': '사용자별 구매 상태 조회 (예: 장바구니 조회)'
            },
            {
                'table': 'purchases',
                'name': 'idx_purchases_round_status',
                'columns': ['purchase_round', 'status'],
                'description': '회차별 구매 상태 조회'
            },
            {
                'table': 'purchases',
                'name': 'idx_purchases_user_round',
                'columns': ['user_id', 'purchase_round'],
                'description': '사용자별 회차 구매 조회'
            },
            {
                'table': 'purchases',
                'name': 'idx_purchases_source',
                'columns': ['source'],
                'description': '입력 소스별 조회 (ai, manual, random, qr)'
            },
            {
                'table': 'purchases',
                'name': 'idx_purchases_winning_rank',
                'columns': ['winning_rank'],
                'description': '당첨 등수별 조회'
            },
            # WinningShop 테이블 복합 인덱스
            {
                'table': 'winning_shops',
                'name': 'idx_winning_shops_round_rank',
                'columns': ['round', 'rank'],
                'description': '회차별 등수별 당첨점 조회'
            },
        ]

        added_count = 0
        skipped_count = 0
        error_count = 0

        for idx_info in indexes_to_add:
            table = idx_info['table']
            name = idx_info['name']
            columns = idx_info['columns']
            description = idx_info['description']

            print(f"📊 {name}")
            print(f"   테이블: {table}")
            print(f"   컬럼: {', '.join(columns)}")
            print(f"   설명: {description}")

            try:
                # 인덱스가 이미 존재하는지 확인
                if check_index_exists(engine, table, name):
                    print(f"   ⏭️  이미 존재함 - 건너뜀")
                    skipped_count += 1
                else:
                    # 인덱스 생성 SQL
                    columns_str = ', '.join(columns)
                    sql = f"CREATE INDEX {name} ON {table} ({columns_str})"

                    db.session.execute(text(sql))
                    db.session.commit()

                    print(f"   ✅ 인덱스 생성 완료")
                    added_count += 1

            except Exception as e:
                print(f"   ❌ 오류 발생: {str(e)}")
                error_count += 1
                db.session.rollback()

            print()

        print("=" * 60)
        print("인덱스 추가 완료")
        print("=" * 60)
        print(f"✅ 추가됨: {added_count}개")
        print(f"⏭️  건너뜀: {skipped_count}개 (이미 존재)")
        print(f"❌ 오류: {error_count}개")
        print()

        if added_count > 0:
            print("💡 성능 개선 효과:")
            print("   - 사용자별 장바구니 조회 속도 향상")
            print("   - 회차별 구매 내역 조회 속도 향상")
            print("   - 당첨 결과 필터링 속도 향상")
            print("   - 입력 소스별 통계 조회 속도 향상")
            print()

        # 인덱스 상태 확인
        print("📋 현재 인덱스 상태:")
        inspector = inspect(engine)

        for table_name in ['purchases', 'winning_shops']:
            indexes = inspector.get_indexes(table_name)
            print(f"\n{table_name} 테이블:")
            for idx in indexes:
                columns = idx.get('column_names', [])
                print(f"  - {idx['name']}: {', '.join(columns)}")


def analyze_query_patterns():
    """자주 사용되는 쿼리 패턴 분석"""
    print("\n" + "=" * 60)
    print("자주 사용되는 쿼리 패턴 분석")
    print("=" * 60)
    print()

    patterns = [
        {
            'description': '사용자 장바구니 조회',
            'query': 'SELECT * FROM purchases WHERE user_id = ? AND status = "DRAFT"',
            'index': 'idx_purchases_user_status',
            'benefit': '매우 높음 (대시보드/구매관리 페이지)'
        },
        {
            'description': '회차별 구매 내역',
            'query': 'SELECT * FROM purchases WHERE purchase_round = ? AND status = "PURCHASED"',
            'index': 'idx_purchases_round_status',
            'benefit': '높음 (구매이력 페이지)'
        },
        {
            'description': '사용자별 당첨 내역',
            'query': 'SELECT * FROM purchases WHERE user_id = ? AND winning_rank IS NOT NULL',
            'index': 'idx_purchases_user_status, idx_purchases_winning_rank',
            'benefit': '높음 (당첨 통계)'
        },
        {
            'description': '입력 방식별 통계',
            'query': 'SELECT COUNT(*) FROM purchases WHERE source = ? GROUP BY source',
            'index': 'idx_purchases_source',
            'benefit': '중간 (통계 페이지)'
        },
        {
            'description': '회차별 당첨점 조회',
            'query': 'SELECT * FROM winning_shops WHERE round = ? AND rank = 1',
            'index': 'idx_winning_shops_round_rank',
            'benefit': '매우 높음 (정보조회 페이지)'
        },
    ]

    for i, pattern in enumerate(patterns, 1):
        print(f"{i}. {pattern['description']}")
        print(f"   쿼리: {pattern['query']}")
        print(f"   인덱스: {pattern['index']}")
        print(f"   성능 향상: {pattern['benefit']}")
        print()


if __name__ == "__main__":
    print("\n🚀 데이터베이스 성능 최적화 시작\n")

    try:
        # 쿼리 패턴 분석
        analyze_query_patterns()

        # 인덱스 추가
        add_composite_indexes()

        print("\n✅ 최적화 완료!")
        print("\n💡 권장사항:")
        print("   1. 프로덕션 환경에서는 트래픽이 적은 시간에 실행하세요")
        print("   2. 인덱스 추가 후 쿼리 성능을 모니터링하세요")
        print("   3. VACUUM 명령으로 데이터베이스를 최적화하세요")
        print()

    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
