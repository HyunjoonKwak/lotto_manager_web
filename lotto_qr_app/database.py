"""
QR 앱 로컬 데이터베이스 관리
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple


class QRDatabase:
    def __init__(self, db_path: str = "qr_data.db"):
        """데이터베이스 초기화"""
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """데이터베이스 테이블 생성"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # QR 스캔 기록 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS qr_scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_number INTEGER NOT NULL,
                scan_date TEXT NOT NULL,
                image_path TEXT,
                qr_raw_data TEXT,
                qr_format TEXT,
                confidence_score REAL DEFAULT 0.0,
                created_at TEXT NOT NULL
            )
        ''')

        # 게임 번호 테이블 (QR에서 인식된 로또 번호들)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_numbers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER NOT NULL,
                game_index INTEGER NOT NULL,
                numbers TEXT NOT NULL,  -- JSON 형태로 저장
                raw_data TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (scan_id) REFERENCES qr_scans (id) ON DELETE CASCADE
            )
        ''')

        # 업로드 상태 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS upload_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER NOT NULL,
                upload_date TEXT,
                upload_success BOOLEAN DEFAULT FALSE,
                upload_message TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (scan_id) REFERENCES qr_scans (id) ON DELETE CASCADE
            )
        ''')

        # 인덱스 생성
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_qr_scans_round ON qr_scans(round_number)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_qr_scans_date ON qr_scans(scan_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_game_numbers_scan ON game_numbers(scan_id)')

        conn.commit()
        conn.close()

    def check_duplicate_scan(self, qr_data: Dict, parsed_lottery_data: Dict) -> Optional[Dict]:
        """동일한 회차의 동일한 용지가 이미 존재하는지 확인"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            round_number = parsed_lottery_data.get('round', 0)

            # 게임 번호들을 정규화하여 비교 (순서 상관없이)
            current_games = set()
            for game in parsed_lottery_data.get('games', []):
                numbers = tuple(sorted(game.get('numbers', [])))
                current_games.add(numbers)

            # 동일한 회차의 모든 스캔 조회
            cursor.execute('''
                SELECT qs.id, qs.scan_date, qs.qr_raw_data
                FROM qr_scans qs
                WHERE qs.round_number = ?
                ORDER BY qs.scan_date DESC
            ''', (round_number,))

            scans = cursor.fetchall()

            for scan_id, scan_date, qr_raw_data in scans:
                # 각 스캔의 게임 번호들 조회
                cursor.execute('''
                    SELECT numbers
                    FROM game_numbers
                    WHERE scan_id = ?
                ''', (scan_id,))

                game_results = cursor.fetchall()
                existing_games = set()

                for (numbers_json,) in game_results:
                    numbers = json.loads(numbers_json)
                    numbers_tuple = tuple(sorted(numbers))
                    existing_games.add(numbers_tuple)

                # 게임 번호 집합이 완전히 일치하면 동일한 용지로 판단
                if current_games == existing_games and len(current_games) > 0:
                    return {
                        'scan_id': scan_id,
                        'scan_date': scan_date,
                        'qr_raw_data': qr_raw_data
                    }

            return None

        except Exception as e:
            raise e
        finally:
            conn.close()

    def save_qr_scan(self, qr_data: Dict, parsed_lottery_data: Dict, image_path: str = None) -> int:
        """QR 스캔 정보 저장"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # QR 스캔 기본 정보 저장
            scan_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO qr_scans
                (round_number, scan_date, image_path, qr_raw_data, qr_format, confidence_score, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                parsed_lottery_data.get('round', 0),
                scan_date,
                image_path,
                json.dumps(qr_data, ensure_ascii=False),
                qr_data.get('format', 'unknown'),
                0.95,  # 기본 신뢰도
                scan_date
            ))

            scan_id = cursor.lastrowid

            # 게임 번호들 저장
            for game in parsed_lottery_data.get('games', []):
                cursor.execute('''
                    INSERT INTO game_numbers
                    (scan_id, game_index, numbers, raw_data, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    scan_id,
                    game.get('game_index', 1),
                    json.dumps(game.get('numbers', [])),
                    game.get('raw_data', ''),
                    scan_date
                ))

            conn.commit()
            return scan_id

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_all_rounds(self) -> List[Dict]:
        """저장된 모든 회차 정보 조회"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                round_number,
                COUNT(*) as scan_count,
                MIN(scan_date) as first_scan,
                MAX(scan_date) as last_scan,
                SUM(CASE WHEN us.upload_success = 1 THEN 1 ELSE 0 END) as uploaded_count
            FROM qr_scans qs
            LEFT JOIN upload_status us ON qs.id = us.scan_id
            WHERE round_number > 0
            GROUP BY round_number
            ORDER BY round_number DESC
        ''')

        rounds = []
        for row in cursor.fetchall():
            rounds.append({
                'round_number': row[0],
                'scan_count': row[1],
                'first_scan': row[2],
                'last_scan': row[3],
                'uploaded_count': row[4] or 0
            })

        conn.close()
        return rounds

    def get_round_details(self, round_number: int) -> Dict:
        """특정 회차의 상세 정보 조회"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 회차 기본 정보
        cursor.execute('''
            SELECT id, scan_date, image_path, qr_format, confidence_score
            FROM qr_scans
            WHERE round_number = ?
            ORDER BY scan_date DESC
        ''', (round_number,))

        scans = []
        for row in cursor.fetchall():
            scan_id = row[0]

            # 해당 스캔의 게임 번호들 조회
            cursor.execute('''
                SELECT game_index, numbers, raw_data
                FROM game_numbers
                WHERE scan_id = ?
                ORDER BY game_index
            ''', (scan_id,))

            games = []
            for game_row in cursor.fetchall():
                games.append({
                    'game_index': game_row[0],
                    'numbers': json.loads(game_row[1]),
                    'raw_data': game_row[2]
                })

            # 업로드 상태 조회
            cursor.execute('''
                SELECT upload_success, upload_date, upload_message
                FROM upload_status
                WHERE scan_id = ?
            ''', (scan_id,))

            upload_info = cursor.fetchone()

            scans.append({
                'scan_id': scan_id,
                'scan_date': row[1],
                'image_path': row[2],
                'qr_format': row[3],
                'confidence_score': row[4],
                'games': games,
                'upload_status': {
                    'uploaded': upload_info[0] if upload_info else False,
                    'upload_date': upload_info[1] if upload_info else None,
                    'message': upload_info[2] if upload_info else None
                } if upload_info else None
            })

        conn.close()

        return {
            'round_number': round_number,
            'scans': scans,
            'total_scans': len(scans),
            'total_games': sum(len(scan['games']) for scan in scans)
        }

    def save_upload_status(self, scan_id: int, success: bool, message: str = ""):
        """업로드 상태 저장"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        upload_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 기존 업로드 상태 삭제 후 새로 추가
        cursor.execute('DELETE FROM upload_status WHERE scan_id = ?', (scan_id,))

        cursor.execute('''
            INSERT INTO upload_status
            (scan_id, upload_date, upload_success, upload_message, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (scan_id, upload_date, success, message, upload_date))

        conn.commit()
        conn.close()

    def save_failed_upload(self, scan_id: int, error_message: str):
        """실패한 업로드 저장 (재시도 대상)"""
        self.save_upload_status(scan_id, False, f"자동 재시도 실패: {error_message}")

    def get_failed_uploads(self) -> List[Dict]:
        """실패한 업로드 목록 조회"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT qs.id, qs.round_number, qs.scan_date, us.upload_message
            FROM qr_scans qs
            INNER JOIN upload_status us ON qs.id = us.scan_id
            WHERE us.upload_success = 0
            ORDER BY qs.scan_date DESC
        ''')

        failed_uploads = []
        for row in cursor.fetchall():
            failed_uploads.append({
                'scan_id': row[0],
                'round_number': row[1],
                'scan_date': row[2],
                'error_message': row[3]
            })

        conn.close()
        return failed_uploads

    def delete_round_data(self, round_number: int) -> int:
        """특정 회차 데이터 삭제"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # CASCADE 제약조건으로 관련 데이터도 자동 삭제됨
        cursor.execute('DELETE FROM qr_scans WHERE round_number = ?', (round_number,))
        deleted_count = cursor.rowcount

        conn.commit()
        conn.close()

        return deleted_count

    def get_statistics(self) -> Dict:
        """데이터베이스 통계 정보"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 전체 통계
        cursor.execute('SELECT COUNT(*) FROM qr_scans')
        total_scans = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(DISTINCT round_number) FROM qr_scans WHERE round_number > 0')
        total_rounds = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM game_numbers')
        total_games = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM upload_status WHERE upload_success = 1')
        successful_uploads = cursor.fetchone()[0]

        # 최근 스캔
        cursor.execute('SELECT MAX(scan_date) FROM qr_scans')
        last_scan_date = cursor.fetchone()[0]

        # 가장 많이 스캔된 회차
        cursor.execute('''
            SELECT round_number, COUNT(*) as scan_count
            FROM qr_scans
            WHERE round_number > 0
            GROUP BY round_number
            ORDER BY scan_count DESC
            LIMIT 1
        ''')
        most_scanned = cursor.fetchone()

        conn.close()

        return {
            'total_scans': total_scans,
            'total_rounds': total_rounds,
            'total_games': total_games,
            'successful_uploads': successful_uploads,
            'last_scan_date': last_scan_date,
            'most_scanned_round': {
                'round_number': most_scanned[0] if most_scanned else None,
                'scan_count': most_scanned[1] if most_scanned else 0
            }
        }

    def get_statistics_for_visualization(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict:
        """시각화를 위한 상세 통계 데이터"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 날짜 필터 조건
        date_filter = ""
        date_and_filter = ""
        params = []
        if start_date and end_date:
            date_filter = "WHERE qs.scan_date BETWEEN ? AND ?"
            date_and_filter = "AND qs.scan_date BETWEEN ? AND ?"
            params = [start_date, end_date]

        # 1. 일별 스캔 횟수
        cursor.execute(f'''
            SELECT DATE(qs.scan_date) as scan_day, COUNT(*) as count
            FROM qr_scans qs
            {date_filter}
            GROUP BY scan_day
            ORDER BY scan_day
        ''', params)
        daily_scans = [{'date': row[0], 'count': row[1]} for row in cursor.fetchall()]

        # 2. 회차별 스캔 분포
        if start_date and end_date:
            cursor.execute(f'''
                SELECT round_number, COUNT(*) as count
                FROM qr_scans qs
                WHERE qs.round_number > 0 AND qs.scan_date BETWEEN ? AND ?
                GROUP BY round_number
                ORDER BY round_number DESC
                LIMIT 20
            ''', params)
        else:
            cursor.execute('''
                SELECT round_number, COUNT(*) as count
                FROM qr_scans
                WHERE round_number > 0
                GROUP BY round_number
                ORDER BY round_number DESC
                LIMIT 20
            ''')
        round_distribution = [{'round': row[0], 'count': row[1]} for row in cursor.fetchall()]

        # 3. 업로드 성공률
        cursor.execute(f'''
            SELECT
                SUM(CASE WHEN us.upload_success = 1 THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN us.upload_success = 0 THEN 1 ELSE 0 END) as fail_count,
                COUNT(CASE WHEN us.id IS NULL THEN 1 END) as pending_count
            FROM qr_scans qs
            LEFT JOIN upload_status us ON qs.id = us.scan_id
            {date_filter}
        ''', params)
        result = cursor.fetchone()
        upload_stats = {
            'success': result[0] or 0,
            'failed': result[1] or 0,
            'pending': result[2] or 0
        }

        # 4. 시간대별 스캔 분포
        cursor.execute(f'''
            SELECT
                CAST(strftime('%H', qs.scan_date) AS INTEGER) as hour,
                COUNT(*) as count
            FROM qr_scans qs
            {date_filter}
            GROUP BY hour
            ORDER BY hour
        ''', params)
        hourly_distribution = [{'hour': row[0], 'count': row[1]} for row in cursor.fetchall()]

        # 5. QR 포맷별 분포
        if start_date and end_date:
            cursor.execute(f'''
                SELECT qr_format, COUNT(*) as count
                FROM qr_scans qs
                WHERE qs.qr_format IS NOT NULL AND qs.scan_date BETWEEN ? AND ?
                GROUP BY qr_format
            ''', params)
        else:
            cursor.execute('''
                SELECT qr_format, COUNT(*) as count
                FROM qr_scans
                WHERE qr_format IS NOT NULL
                GROUP BY qr_format
            ''')
        format_distribution = [{'format': row[0], 'count': row[1]} for row in cursor.fetchall()]

        # 6. 상위 10개 회차 (스캔 횟수 기준)
        if start_date and end_date:
            cursor.execute(f'''
                SELECT round_number, COUNT(*) as scan_count
                FROM qr_scans qs
                WHERE qs.round_number > 0 AND qs.scan_date BETWEEN ? AND ?
                GROUP BY round_number
                ORDER BY scan_count DESC
                LIMIT 10
            ''', params)
        else:
            cursor.execute('''
                SELECT round_number, COUNT(*) as scan_count
                FROM qr_scans
                WHERE round_number > 0
                GROUP BY round_number
                ORDER BY scan_count DESC
                LIMIT 10
            ''')
        top_rounds = [{'round': row[0], 'count': row[1]} for row in cursor.fetchall()]

        conn.close()

        return {
            'daily_scans': daily_scans,
            'round_distribution': round_distribution,
            'upload_stats': upload_stats,
            'hourly_distribution': hourly_distribution,
            'format_distribution': format_distribution,
            'top_rounds': top_rounds
        }

    def cleanup_old_data(self, days: int = 30) -> int:
        """오래된 데이터 정리 (기본 30일)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            DELETE FROM qr_scans
            WHERE created_at < datetime(?, '-{} days')
        '''.format(days), (cutoff_date,))

        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()

        return deleted_count

    def export_to_csv(self, file_path: str, round_filter: Optional[int] = None) -> bool:
        """CSV 파일로 내보내기"""
        import csv

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 데이터 조회
            if round_filter:
                query = '''
                    SELECT qs.round_number, qs.scan_date, gn.game_index, gn.numbers, us.upload_success
                    FROM qr_scans qs
                    INNER JOIN game_numbers gn ON qs.id = gn.scan_id
                    LEFT JOIN upload_status us ON qs.id = us.scan_id
                    WHERE qs.round_number = ?
                    ORDER BY qs.round_number DESC, gn.game_index
                '''
                cursor.execute(query, (round_filter,))
            else:
                query = '''
                    SELECT qs.round_number, qs.scan_date, gn.game_index, gn.numbers, us.upload_success
                    FROM qr_scans qs
                    INNER JOIN game_numbers gn ON qs.id = gn.scan_id
                    LEFT JOIN upload_status us ON qs.id = us.scan_id
                    ORDER BY qs.round_number DESC, gn.game_index
                '''
                cursor.execute(query)

            rows = cursor.fetchall()
            conn.close()

            # CSV 작성
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile)

                # 헤더
                writer.writerow(['회차', '스캔일시', '게임번호', '번호1', '번호2', '번호3', '번호4', '번호5', '번호6', '업로드여부'])

                # 데이터
                for row in rows:
                    round_num, scan_date, game_idx, numbers_json, uploaded = row
                    numbers = json.loads(numbers_json)

                    csv_row = [
                        round_num,
                        scan_date,
                        game_idx,
                        *numbers,
                        '예' if uploaded else '아니오'
                    ]
                    writer.writerow(csv_row)

            return True

        except Exception as e:
            print(f"CSV export error: {e}")
            return False

    def export_to_json(self, file_path: str, round_filter: Optional[int] = None) -> bool:
        """JSON 파일로 내보내기 (전체 메타데이터 포함)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 회차별로 조회
            if round_filter:
                cursor.execute('SELECT DISTINCT round_number FROM qr_scans WHERE round_number = ? ORDER BY round_number DESC', (round_filter,))
            else:
                cursor.execute('SELECT DISTINCT round_number FROM qr_scans ORDER BY round_number DESC')

            rounds = [r[0] for r in cursor.fetchall()]

            export_data = {
                'export_date': datetime.now().isoformat(),
                'total_rounds': len(rounds),
                'rounds': []
            }

            for round_num in rounds:
                round_data = self.get_round_details(round_num)
                export_data['rounds'].append(round_data)

            conn.close()

            # JSON 작성
            with open(file_path, 'w', encoding='utf-8') as jsonfile:
                json.dump(export_data, jsonfile, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            print(f"JSON export error: {e}")
            return False
