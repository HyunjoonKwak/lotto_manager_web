#!/usr/bin/env python3
"""
Purchase 모델 마이그레이션 스크립트 (Phase 1.1)

새로운 필드 추가:
- status: 구매 상태 (DRAFT, PURCHASED, CHECKED)
- is_real_purchase: 실제 구매 여부
- purchase_location: 구매처
- cost: 구매 금액

기존 데이터 변환:
- source 필드 정리 ('수동입력' → 'manual', 'AI추천' → 'ai' 등)
- 기본값 설정
"""

import sys
import os
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Purchase


def backup_database():
    """데이터베이스 백업"""
    app = create_app()
    with app.app_context():
        db_path = os.path.join(app.instance_path, 'lotto.db')
        if os.path.exists(db_path):
            backup_path = os.path.join(
                app.instance_path,
                f'lotto_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
            )
            import shutil
            shutil.copy2(db_path, backup_path)
            print(f"✅ 데이터베이스 백업 완료: {backup_path}")
            return backup_path
        else:
            print("⚠️  데이터베이스 파일이 없습니다. 새로 생성됩니다.")
            return None


def add_new_columns():
    """새로운 컬럼 추가"""
    app = create_app()
    with app.app_context():
        try:
            # SQLite는 ALTER TABLE로 컬럼 추가 시 제약조건 제한이 있음
            # 따라서 직접 SQL로 실행

            # status 컬럼 추가
            try:
                db.session.execute(db.text(
                    "ALTER TABLE purchases ADD COLUMN status VARCHAR(20) DEFAULT 'DRAFT'"
                ))
                print("✅ status 컬럼 추가")
            except Exception as e:
                if "duplicate column" in str(e).lower():
                    print("ℹ️  status 컬럼이 이미 존재합니다")
                else:
                    raise

            # is_real_purchase 컬럼 추가
            try:
                db.session.execute(db.text(
                    "ALTER TABLE purchases ADD COLUMN is_real_purchase BOOLEAN DEFAULT 0"
                ))
                print("✅ is_real_purchase 컬럼 추가")
            except Exception as e:
                if "duplicate column" in str(e).lower():
                    print("ℹ️  is_real_purchase 컬럼이 이미 존재합니다")
                else:
                    raise

            # purchase_location 컬럼 추가
            try:
                db.session.execute(db.text(
                    "ALTER TABLE purchases ADD COLUMN purchase_location VARCHAR(200)"
                ))
                print("✅ purchase_location 컬럼 추가")
            except Exception as e:
                if "duplicate column" in str(e).lower():
                    print("ℹ️  purchase_location 컬럼이 이미 존재합니다")
                else:
                    raise

            # cost 컬럼 추가
            try:
                db.session.execute(db.text(
                    "ALTER TABLE purchases ADD COLUMN cost INTEGER DEFAULT 1000"
                ))
                print("✅ cost 컬럼 추가")
            except Exception as e:
                if "duplicate column" in str(e).lower():
                    print("ℹ️  cost 컬럼이 이미 존재합니다")
                else:
                    raise

            db.session.commit()
            print("\n✅ 모든 컬럼 추가 완료\n")

        except Exception as e:
            db.session.rollback()
            print(f"❌ 컬럼 추가 실패: {e}")
            raise


def migrate_existing_data():
    """기존 데이터 변환"""
    app = create_app()
    with app.app_context():
        try:
            purchases = Purchase.query.all()
            total = len(purchases)
            print(f"📊 총 {total}건의 구매 기록 마이그레이션 시작...\n")

            updated_count = 0

            for i, purchase in enumerate(purchases, 1):
                updated = False

                # 1. source 필드 정규화
                if purchase.source:
                    source_map = {
                        '수동입력': 'manual',
                        'AI추천': 'ai',
                        'QR': 'qr',
                        '랜덤': 'random',
                        '랜덤생성': 'random',
                        'local_collector': 'qr',  # QR 스캔으로 통일
                    }

                    old_source = purchase.source
                    for old, new in source_map.items():
                        if old in purchase.source:
                            purchase.source = new
                            updated = True
                            break
                else:
                    # source가 없으면 purchase_method 기반으로 설정
                    if purchase.purchase_method:
                        if 'AI' in purchase.purchase_method or '추천' in purchase.purchase_method:
                            purchase.source = 'ai'
                        elif '수동' in purchase.purchase_method:
                            purchase.source = 'manual'
                        elif 'QR' in purchase.purchase_method or purchase.recognition_method == 'QR':
                            purchase.source = 'qr'
                        else:
                            purchase.source = 'manual'  # 기본값
                        updated = True

                # 2. status 설정
                if purchase.result_checked:
                    purchase.status = 'CHECKED'
                elif purchase.recognition_method == 'QR' or purchase.source == 'qr':
                    # QR 스캔은 실제 구매로 간주
                    purchase.status = 'PURCHASED'
                    purchase.is_real_purchase = True
                else:
                    # 그 외는 임시저장으로 간주
                    purchase.status = 'DRAFT'
                    purchase.is_real_purchase = False

                updated = True

                # 3. cost 설정
                if not purchase.cost:
                    purchase.cost = 1000
                    updated = True

                if updated:
                    updated_count += 1

                # 진행 상황 표시 (10%마다)
                if i % max(1, total // 10) == 0:
                    print(f"  진행중... {i}/{total} ({i*100//total}%)")

            db.session.commit()
            print(f"\n✅ 데이터 마이그레이션 완료: {updated_count}/{total}건 업데이트\n")

            # 마이그레이션 결과 요약
            print("📊 마이그레이션 결과 요약:")
            draft_count = Purchase.query.filter_by(status='DRAFT').count()
            purchased_count = Purchase.query.filter_by(status='PURCHASED').count()
            checked_count = Purchase.query.filter_by(status='CHECKED').count()

            print(f"  - DRAFT (임시저장): {draft_count}건")
            print(f"  - PURCHASED (구매완료): {purchased_count}건")
            print(f"  - CHECKED (결과확인): {checked_count}건")

            source_stats = db.session.query(
                Purchase.source,
                db.func.count(Purchase.id)
            ).group_by(Purchase.source).all()

            print(f"\n  입력 소스별:")
            for source, count in source_stats:
                print(f"  - {source or '(없음)'}: {count}건")

        except Exception as e:
            db.session.rollback()
            print(f"❌ 데이터 마이그레이션 실패: {e}")
            raise


def create_indexes():
    """인덱스 생성"""
    app = create_app()
    with app.app_context():
        try:
            # status 인덱스 (이미 모델에 정의되어 있지만 명시적으로 생성)
            db.session.execute(db.text(
                "CREATE INDEX IF NOT EXISTS idx_purchases_status ON purchases(status)"
            ))

            # 복합 인덱스: user_id + status (자주 사용되는 쿼리 최적화)
            db.session.execute(db.text(
                "CREATE INDEX IF NOT EXISTS idx_purchases_user_status ON purchases(user_id, status)"
            ))

            # 복합 인덱스: purchase_round + status
            db.session.execute(db.text(
                "CREATE INDEX IF NOT EXISTS idx_purchases_round_status ON purchases(purchase_round, status)"
            ))

            db.session.commit()
            print("✅ 인덱스 생성 완료\n")

        except Exception as e:
            db.session.rollback()
            print(f"⚠️  인덱스 생성 실패 (무시 가능): {e}")


def verify_migration():
    """마이그레이션 검증"""
    app = create_app()
    with app.app_context():
        try:
            print("🔍 마이그레이션 검증 중...\n")

            # 1. 모든 레코드에 status가 있는지 확인
            null_status = Purchase.query.filter(
                (Purchase.status == None) | (Purchase.status == '')
            ).count()

            if null_status > 0:
                print(f"⚠️  status가 없는 레코드: {null_status}건")
                return False
            else:
                print("✅ 모든 레코드에 status 존재")

            # 2. source 필드 정규화 확인
            invalid_sources = Purchase.query.filter(
                ~Purchase.source.in_(['manual', 'ai', 'qr', 'random', None])
            ).all()

            if invalid_sources:
                print(f"⚠️  비정규화된 source: {len(invalid_sources)}건")
                for p in invalid_sources[:5]:  # 처음 5개만 표시
                    print(f"    ID {p.id}: {p.source}")
                return False
            else:
                print("✅ source 필드 정규화 완료")

            # 3. 샘플 데이터 확인
            sample = Purchase.query.first()
            if sample:
                print(f"\n📋 샘플 데이터:")
                print(f"  ID: {sample.id}")
                print(f"  회차: {sample.purchase_round}")
                print(f"  번호: {sample.numbers}")
                print(f"  source: {sample.source}")
                print(f"  status: {sample.status}")
                print(f"  is_real_purchase: {sample.is_real_purchase}")
                print(f"  cost: {sample.cost}")

            print("\n✅ 마이그레이션 검증 완료!")
            return True

        except Exception as e:
            print(f"❌ 검증 실패: {e}")
            return False


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("Purchase 모델 마이그레이션 (Phase 1.1)")
    print("=" * 60)
    print()

    # 확인 메시지
    print("다음 작업을 수행합니다:")
    print("  1. 데이터베이스 백업")
    print("  2. 새로운 컬럼 추가 (status, is_real_purchase, purchase_location, cost)")
    print("  3. 기존 데이터 변환")
    print("  4. 인덱스 생성")
    print("  5. 마이그레이션 검증")
    print()

    response = input("계속하시겠습니까? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("❌ 마이그레이션 취소됨")
        return

    print("\n" + "=" * 60)
    print("마이그레이션 시작")
    print("=" * 60 + "\n")

    try:
        # 1. 백업
        backup_path = backup_database()

        # 2. 컬럼 추가
        add_new_columns()

        # 3. 데이터 마이그레이션
        migrate_existing_data()

        # 4. 인덱스 생성
        create_indexes()

        # 5. 검증
        if verify_migration():
            print("\n" + "=" * 60)
            print("✅ 마이그레이션 성공!")
            print("=" * 60)
            if backup_path:
                print(f"\n💾 백업 파일: {backup_path}")
                print("   문제 발생 시 이 파일로 복원 가능합니다.")
        else:
            print("\n" + "=" * 60)
            print("⚠️  마이그레이션은 완료되었으나 검증에서 경고 발생")
            print("=" * 60)

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ 마이그레이션 실패: {e}")
        print("=" * 60)
        if backup_path:
            print(f"\n💾 백업 파일로 복원하세요: {backup_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
