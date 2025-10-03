"""
로또 구매 용지 텍스트 파서
텍스트로 붙여넣은 로또 구매 정보를 파싱
"""

import re
from typing import Dict, List, Optional
from datetime import datetime


class LottoTextParser:
    """로또 구매 용지 텍스트 파서"""

    def __init__(self):
        self.round_number = None
        self.purchase_date = None
        self.draw_date = None
        self.games = []

    def parse(self, text: str) -> Dict:
        """
        로또 구매 용지 텍스트 파싱

        예시 입력:
        복권 로또 645제 1191회
        발 행 일 : 2025/09/27 (토) 10:08:16
        추 첨 일 : 2025/09/27

        A 수동 (낙첨)379152635
        B 수동 (낙첨)3711121526
        C 자동 (낙첨)2517223641
        """
        try:
            # 초기화
            self.round_number = None
            self.purchase_date = None
            self.draw_date = None
            self.games = []

            lines = text.strip().split('\n')

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # 회차 파싱
                if '제' in line and '회' in line:
                    self._parse_round(line)

                # 발행일 파싱
                elif '발 행 일' in line or '발행일' in line:
                    self._parse_purchase_date(line)

                # 추첨일 파싱
                elif '추 첨 일' in line or '추첨일' in line:
                    self._parse_draw_date(line)

                # 게임 번호 파싱 (A, B, C, D, E로 시작)
                elif re.match(r'^[A-E]\s', line):
                    game_data = self._parse_game_line(line)
                    if game_data:
                        self.games.append(game_data)

            # 검증
            if not self.round_number:
                return {
                    "success": False,
                    "error": "회차 정보를 찾을 수 없습니다."
                }

            if not self.games:
                return {
                    "success": False,
                    "error": "게임 번호를 찾을 수 없습니다."
                }

            return {
                "success": True,
                "data": {
                    "round": self.round_number,
                    "purchase_date": self.purchase_date,
                    "draw_date": self.draw_date,
                    "games": self.games
                }
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"파싱 오류: {str(e)}"
            }

    def _parse_round(self, line: str):
        """회차 파싱: '복권 로또 645제 1191회' -> 1191"""
        match = re.search(r'제\s*(\d+)\s*회', line)
        if match:
            self.round_number = int(match.group(1))

    def _parse_purchase_date(self, line: str):
        """발행일 파싱: '발 행 일 : 2025/09/27 (토) 10:08:16' -> '2025-09-27'"""
        # 날짜 패턴: YYYY/MM/DD 또는 YYYY-MM-DD
        match = re.search(r'(\d{4})[/-](\d{2})[/-](\d{2})', line)
        if match:
            year, month, day = match.groups()
            self.purchase_date = f"{year}-{month}-{day}"

    def _parse_draw_date(self, line: str):
        """추첨일 파싱: '추 첨 일 : 2025/09/27' -> '2025-09-27'"""
        match = re.search(r'(\d{4})[/-](\d{2})[/-](\d{2})', line)
        if match:
            year, month, day = match.groups()
            self.draw_date = f"{year}-{month}-{day}"

    def _parse_game_line(self, line: str) -> Optional[Dict]:
        """
        게임 라인 파싱
        예: 'A 수동 (낙첨)379152635' -> {'game_type': 'A', 'mode': '수동', 'numbers': [3, 7, 9, 15, 26, 35]}
        예: 'A 수동 (낙첨) 03 07 09 15 26 35' -> 공백으로 구분된 경우도 처리
        """
        try:
            # 게임 타입 추출 (A, B, C, D, E)
            game_type = line[0]

            # 자동/수동 판별
            mode = '자동' if '자동' in line else '수동'

            # 패턴 1: 괄호 뒤에 연속된 숫자 (공백 없음)
            # 'A 수동 (낙첨)379152635'
            match = re.search(r'\([^)]*\)\s*(\d+)', line)
            if match:
                number_string = match.group(1)
                # 공백이 없으면 연속 숫자로 파싱
                if ' ' not in number_string:
                    numbers = self._extract_numbers(number_string)
                else:
                    # 공백이 있으면 분리
                    numbers = [int(n) for n in number_string.split() if n.isdigit()]
            else:
                # 패턴 2: 괄호 없이 숫자만
                # 'A 수동 379152635' 또는 'A 수동 03 07 09 15 26 35'
                match = re.search(r'[A-E]\s+(?:수동|자동)\s+(.+)', line)
                if match:
                    number_part = match.group(1).strip()
                    # 공백으로 구분되어 있는지 확인
                    if ' ' in number_part:
                        # 공백으로 분리된 숫자
                        numbers = [int(n.strip()) for n in number_part.split() if n.strip().isdigit()]
                    else:
                        # 연속된 숫자
                        numbers = self._extract_numbers(number_part)
                else:
                    return None

            # 번호 개수 검증
            if len(numbers) == 6:
                # 번호 범위 검증 (1-45)
                if all(1 <= n <= 45 for n in numbers):
                    return {
                        'game_type': game_type,
                        'mode': mode,
                        'numbers': sorted(numbers)  # 정렬
                    }

            return None

        except Exception as e:
            print(f"게임 라인 파싱 오류: {line} - {e}")
            return None

    def _extract_numbers(self, number_string: str) -> List[int]:
        """
        연속된 숫자 문자열에서 로또 번호 추출 (백트래킹 사용)
        '379152635' -> [3, 7, 9, 15, 26, 35]
        '0103051015' -> [1, 3, 5, 10, 15]

        전략: 백트래킹으로 정확히 6개의 유효한 번호를 찾음
        """
        def backtrack(index: int, current: List[int]) -> Optional[List[int]]:
            """백트래킹으로 6개 번호 찾기"""
            # 성공 조건: 6개 번호를 찾고, 문자열 끝에 도달
            if len(current) == 6:
                if index == len(number_string):
                    return current[:]
                else:
                    return None

            # 실패 조건: 문자열 끝에 도달했는데 6개 미만
            if index >= len(number_string):
                return None

            # 0으로 시작하는 2자리 (01-09)
            if number_string[index] == '0' and index + 1 < len(number_string):
                digit = int(number_string[index+1])
                if 1 <= digit <= 9:
                    result = backtrack(index + 2, current + [digit])
                    if result:
                        return result

            # 2자리 시도 (10-45)
            if index + 1 < len(number_string):
                two_digit = int(number_string[index:index+2])
                if 10 <= two_digit <= 45:
                    result = backtrack(index + 2, current + [two_digit])
                    if result:
                        return result

            # 1자리 시도 (1-9)
            one_digit = int(number_string[index])
            if 1 <= one_digit <= 9:
                result = backtrack(index + 1, current + [one_digit])
                if result:
                    return result

            return None

        result = backtrack(0, [])
        return result if result else []


def parse_lottery_text(text: str) -> Dict:
    """
    편의 함수: 로또 텍스트 파싱
    """
    parser = LottoTextParser()
    return parser.parse(text)


if __name__ == "__main__":
    # 테스트
    test_text = """
인터넷 로또 6/45 구매번호
복권 로또 645제 1191회
발 행 일 : 2025/09/27 (토) 10:08:16
추 첨 일 : 2025/09/27
지급 기한 : 2026/09/28
53715 78497 90043 65374 14132 07073

A 수동 (낙첨)379152635
B 수동 (낙첨)3711121526
C 자동 (낙첨)2517223641
D 자동 (낙첨)132224283338
E 수동 (낙첨)121517303135
    """

    result = parse_lottery_text(test_text)
    print("파싱 결과:")
    print(result)
