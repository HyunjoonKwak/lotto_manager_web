"""
로또 구매 용지 텍스트 파서 (웹앱용)
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
        """
        try:
            # 게임 타입 추출 (A, B, C, D, E)
            game_type = line[0]

            # 자동/수동 판별
            mode = '자동' if '자동' in line else '수동'

            # 패턴 1: 괄호 뒤에 연속된 숫자 (공백 없음)
            match = re.search(r'\([^)]*\)\s*(\d+)', line)
            if match:
                number_string = match.group(1)
                if ' ' not in number_string:
                    numbers = self._extract_numbers(number_string)
                else:
                    numbers = [int(n) for n in number_string.split() if n.isdigit()]
            else:
                # 패턴 2: 괄호 없이 숫자만
                match = re.search(r'[A-E]\s+(?:수동|자동)\s+(.+)', line)
                if match:
                    number_part = match.group(1).strip()
                    if ' ' in number_part:
                        numbers = [int(n.strip()) for n in number_part.split() if n.strip().isdigit()]
                    else:
                        numbers = self._extract_numbers(number_part)
                else:
                    return None

            # 번호 개수 및 범위 검증
            if len(numbers) == 6 and all(1 <= n <= 45 for n in numbers):
                return {
                    'game_type': game_type,
                    'mode': mode,
                    'numbers': sorted(numbers)
                }

            return None

        except Exception as e:
            return None

    def _extract_numbers(self, number_string: str) -> List[int]:
        """
        연속된 숫자 문자열에서 로또 번호 추출 (백트래킹 사용)
        """
        def backtrack(index: int, current: List[int]) -> Optional[List[int]]:
            if len(current) == 6:
                return current[:] if index == len(number_string) else None

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
    """편의 함수: 로또 텍스트 파싱"""
    parser = LottoTextParser()
    return parser.parse(text)
