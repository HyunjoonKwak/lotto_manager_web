"""
QR code processing for lottery ticket information
"""

import cv2
import numpy as np
from pyzbar import pyzbar
from typing import Dict, Optional, List
import re
from datetime import datetime


class QRProcessor:
    def __init__(self):
        pass

    def extract_qr_data(self, image_path: str) -> Dict:
        """
        이미지에서 QR 코드를 찾아 데이터 추출
        """
        try:
            # 이미지 로드
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"이미지를 로드할 수 없습니다: {image_path}")

            # QR 코드 디코딩
            qr_codes = pyzbar.decode(image)

            if not qr_codes:
                # 그레이스케일로 다시 시도
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                qr_codes = pyzbar.decode(gray)

            if not qr_codes:
                # 이진화 후 다시 시도
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                qr_codes = pyzbar.decode(binary)

            extracted_data = []
            for qr_code in qr_codes:
                data = qr_code.data.decode('utf-8')
                qr_info = self._parse_lottery_qr(data)
                if qr_info:
                    extracted_data.append(qr_info)

            return {
                "success": True,
                "qr_count": len(qr_codes),
                "data": extracted_data[0] if extracted_data else None,
                "all_data": extracted_data,
                "raw_codes": [qr.data.decode('utf-8') for qr in qr_codes]
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "qr_count": 0,
                "data": None,
                "all_data": [],
                "raw_codes": []
            }

    def _parse_lottery_qr(self, qr_data: str) -> Optional[Dict]:
        """
        로또 QR 코드 데이터 파싱
        """
        try:
            # 로또 QR 코드는 여러 형식이 있을 수 있음
            # 일반적인 형식들을 처리

            # 형식 1: 회차|구매일시|게임수|... 형태
            if '|' in qr_data:
                return self._parse_pipe_format(qr_data)

            # 형식 2: URL 형태
            if 'dhlottery.co.kr' in qr_data or 'lottery' in qr_data.lower():
                return self._parse_url_format(qr_data)

            # 형식 3: JSON 형태
            if qr_data.startswith('{') and qr_data.endswith('}'):
                return self._parse_json_format(qr_data)

            # 형식 4: 단순 숫자 나열
            if re.match(r'^\d+$', qr_data):
                return self._parse_number_format(qr_data)

            # 기타 형식 - 회차 번호만 추출 시도
            round_match = re.search(r'(\d{3,4})', qr_data)
            if round_match:
                return {
                    "round": int(round_match.group(1)),
                    "format": "unknown",
                    "raw_data": qr_data
                }

            return None

        except Exception as e:
            print(f"QR 파싱 오류: {e}")
            return None

    def _parse_pipe_format(self, qr_data: str) -> Optional[Dict]:
        """파이프(|) 구분자 형식 파싱"""
        try:
            parts = qr_data.split('|')
            if len(parts) < 3:
                return None

            result = {
                "format": "pipe",
                "raw_data": qr_data
            }

            # 첫 번째 부분이 회차인 경우가 많음
            if parts[0].isdigit() and len(parts[0]) >= 3:
                result["round"] = int(parts[0])

            # 날짜 형식 찾기
            for part in parts:
                # YYYYMMDD 형식
                if re.match(r'^\d{8}$', part):
                    try:
                        date_obj = datetime.strptime(part, '%Y%m%d')
                        result["purchase_date"] = date_obj.strftime('%Y-%m-%d')
                    except:
                        pass

                # YYYY-MM-DD 형식
                elif re.match(r'^\d{4}-\d{2}-\d{2}$', part):
                    result["purchase_date"] = part

                # 게임 수
                elif part.isdigit() and 1 <= int(part) <= 5:
                    result["game_count"] = int(part)

            return result

        except Exception as e:
            print(f"Pipe 형식 파싱 오류: {e}")
            return None

    def _parse_url_format(self, qr_data: str) -> Optional[Dict]:
        """URL 형식 파싱"""
        try:
            result = {
                "format": "url",
                "raw_data": qr_data,
                "url": qr_data
            }

            # URL에서 파라미터 추출
            # 회차 번호
            round_match = re.search(r'[?&]round=(\d+)', qr_data)
            if round_match:
                result["round"] = int(round_match.group(1))

            # 기타 파라미터들
            date_match = re.search(r'[?&]date=(\d{4}-\d{2}-\d{2})', qr_data)
            if date_match:
                result["purchase_date"] = date_match.group(1)

            return result

        except Exception as e:
            print(f"URL 형식 파싱 오류: {e}")
            return None

    def _parse_json_format(self, qr_data: str) -> Optional[Dict]:
        """JSON 형식 파싱"""
        try:
            import json
            data = json.loads(qr_data)

            result = {
                "format": "json",
                "raw_data": qr_data
            }

            # 일반적인 필드명들 확인
            field_mappings = {
                "round": ["round", "회차", "drwNo"],
                "purchase_date": ["date", "purchase_date", "구매일", "buyDate"],
                "game_count": ["games", "game_count", "게임수", "gameCount"]
            }

            for key, possible_fields in field_mappings.items():
                for field in possible_fields:
                    if field in data:
                        result[key] = data[field]
                        break

            return result

        except Exception as e:
            print(f"JSON 형식 파싱 오류: {e}")
            return None

    def _parse_number_format(self, qr_data: str) -> Optional[Dict]:
        """순수 숫자 형식 파싱"""
        try:
            # 길이에 따라 다르게 처리
            if len(qr_data) >= 4:
                # 앞 3-4자리를 회차로 가정
                round_part = qr_data[:4] if qr_data[3] != '0' else qr_data[:3]

                return {
                    "format": "number",
                    "raw_data": qr_data,
                    "round": int(round_part)
                }

            return None

        except Exception as e:
            print(f"숫자 형식 파싱 오류: {e}")
            return None

    def enhance_qr_detection(self, image_path: str) -> Dict:
        """
        QR 코드 검출을 위한 이미지 향상
        """
        try:
            image = cv2.imread(image_path)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # 여러 방법으로 시도
            methods = [
                ("original", gray),
                ("equalized", cv2.equalizeHist(gray)),
                ("gaussian", cv2.GaussianBlur(gray, (3, 3), 0)),
                ("bilateral", cv2.bilateralFilter(gray, 9, 75, 75))
            ]

            all_results = []

            for method_name, processed_img in methods:
                qr_codes = pyzbar.decode(processed_img)
                if qr_codes:
                    for qr_code in qr_codes:
                        data = qr_code.data.decode('utf-8')
                        parsed = self._parse_lottery_qr(data)
                        if parsed:
                            parsed["detection_method"] = method_name
                            all_results.append(parsed)

            # 중복 제거 (같은 데이터)
            unique_results = []
            seen_data = set()

            for result in all_results:
                raw_data = result.get("raw_data", "")
                if raw_data not in seen_data:
                    seen_data.add(raw_data)
                    unique_results.append(result)

            return {
                "success": len(unique_results) > 0,
                "results": unique_results,
                "methods_tried": len(methods),
                "total_detections": len(all_results)
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "results": [],
                "methods_tried": 0,
                "total_detections": 0
            }
