"""
API client for communicating with the web app
"""

import requests
import json
import hashlib
from typing import Dict, List, Optional
from datetime import datetime
from config import API_ENDPOINT, WEB_APP_URL


class APIClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'LottoOCR-LocalApp/1.0'
        })

        if api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {api_key}'
            })

    def upload_purchase_data(self, purchase_data: Dict) -> Dict:
        """
        구매 데이터를 웹 앱에 업로드
        """
        try:
            # 데이터 검증
            validation_result = self._validate_purchase_data(purchase_data)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": "데이터 검증 실패",
                    "details": validation_result["errors"]
                }

            # API 호출
            response = self.session.post(API_ENDPOINT, json=purchase_data, timeout=30)

            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json(),
                    "message": "구매 데이터가 성공적으로 업로드되었습니다."
                }
            elif response.status_code == 400:
                return {
                    "success": False,
                    "error": "잘못된 요청",
                    "details": response.json().get("error", "Unknown error")
                }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "error": "인증 실패",
                    "details": "API 키를 확인해주세요."
                }
            elif response.status_code == 409:
                return {
                    "success": False,
                    "error": "중복 데이터",
                    "details": "이미 등록된 구매 데이터입니다."
                }
            else:
                return {
                    "success": False,
                    "error": f"서버 오류 ({response.status_code})",
                    "details": response.text
                }

        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error": "연결 실패",
                "details": f"웹 앱 서버({WEB_APP_URL})에 연결할 수 없습니다."
            }
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "요청 시간 초과",
                "details": "서버 응답 시간이 초과되었습니다."
            }
        except Exception as e:
            return {
                "success": False,
                "error": "예상치 못한 오류",
                "details": str(e)
            }

    def test_connection(self) -> Dict:
        """
        웹 앱 서버 연결 테스트
        """
        try:
            health_url = f"{WEB_APP_URL}/health"
            response = self.session.get(health_url, timeout=10)

            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "서버 연결 성공",
                    "server_info": response.json() if response.headers.get('content-type') == 'application/json' else None
                }
            else:
                return {
                    "success": False,
                    "error": f"서버 응답 오류 ({response.status_code})"
                }

        except Exception as e:
            return {
                "success": False,
                "error": "연결 테스트 실패",
                "details": str(e)
            }

    def _validate_purchase_data(self, data: Dict) -> Dict:
        """
        업로드할 구매 데이터 검증
        """
        errors = []

        # 필수 필드 확인
        required_fields = ["games"]
        for field in required_fields:
            if field not in data:
                errors.append(f"필수 필드 누락: {field}")

        # 게임 데이터 검증
        games = data.get("games", [])
        if not games:
            errors.append("최소 1개의 게임이 필요합니다.")
        elif len(games) > 5:
            errors.append("최대 5개의 게임만 허용됩니다.")

        for i, game in enumerate(games):
            if not isinstance(game, dict):
                errors.append(f"게임 {i+1}: 잘못된 형식")
                continue

            numbers = game.get("numbers", [])
            if not numbers:
                errors.append(f"게임 {i+1}: 번호가 없습니다.")
                continue

            if len(numbers) != 6:
                errors.append(f"게임 {i+1}: 번호는 6개여야 합니다. (현재: {len(numbers)}개)")

            # 번호 범위 확인
            for num in numbers:
                if not isinstance(num, int) or not (1 <= num <= 45):
                    errors.append(f"게임 {i+1}: 잘못된 번호 {num}")

            # 중복 번호 확인
            if len(set(numbers)) != len(numbers):
                errors.append(f"게임 {i+1}: 중복 번호가 있습니다.")

        # 회차 검증
        round_num = data.get("round")
        if round_num is not None:
            if not isinstance(round_num, int) or round_num < 1:
                errors.append(f"잘못된 회차 번호: {round_num}")

        # 구매일 검증
        purchase_date = data.get("purchase_date")
        if purchase_date is not None:
            try:
                datetime.strptime(purchase_date, '%Y-%m-%d')
            except ValueError:
                errors.append(f"잘못된 구매일 형식: {purchase_date}")

        return {
            "valid": len(errors) == 0,
            "errors": errors
        }

    def create_purchase_data(self, games: List[Dict], round_num: Optional[int] = None,
                           purchase_date: Optional[str] = None, qr_data: Optional[Dict] = None,
                           image_path: Optional[str] = None) -> Dict:
        """
        구매 데이터 객체 생성
        """
        purchase_data = {
            "games": games,
            "source": "ocr_app",
            "timestamp": datetime.now().isoformat()
        }

        # 회차 정보
        if round_num:
            purchase_data["round"] = round_num
        elif qr_data and "round" in qr_data:
            purchase_data["round"] = qr_data["round"]

        # 구매일
        if purchase_date:
            purchase_data["purchase_date"] = purchase_date
        elif qr_data and "purchase_date" in qr_data:
            purchase_data["purchase_date"] = qr_data["purchase_date"]
        else:
            purchase_data["purchase_date"] = datetime.now().strftime('%Y-%m-%d')

        # QR 데이터가 있으면 추가 정보 포함
        if qr_data:
            purchase_data["qr_info"] = {
                "format": qr_data.get("format"),
                "raw_data": qr_data.get("raw_data"),
                "detection_method": qr_data.get("detection_method")
            }

        # 이미지 해시 (중복 방지용)
        if image_path:
            try:
                purchase_data["image_hash"] = self._calculate_image_hash(image_path)
            except:
                pass

        return purchase_data

    def _calculate_image_hash(self, image_path: str) -> str:
        """이미지 파일의 해시값 계산"""
        hash_sha256 = hashlib.sha256()
        with open(image_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def get_latest_round(self) -> Optional[int]:
        """웹 앱에서 최신 회차 정보 가져오기"""
        try:
            url = f"{WEB_APP_URL}/api/data-stats"
            response = self.session.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return data.get("latest_round")

        except Exception as e:
            print(f"최신 회차 조회 실패: {e}")

        return None

    def validate_round(self, round_num: int) -> bool:
        """회차 번호 유효성 검증"""
        try:
            latest_round = self.get_latest_round()
            if latest_round:
                return 1 <= round_num <= latest_round
            else:
                # 웹 앱에서 정보를 가져올 수 없는 경우 기본 범위로 검증
                return 1 <= round_num <= 9999

        except:
            return 1 <= round_num <= 9999

    def upload_qr_data(self, qr_data: Dict) -> Dict:
        """QR 데이터 업로드"""
        try:
            url = f"{self.base_url}/api/purchases/qr"
            response = requests.post(url, json=qr_data, timeout=30)

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "message": result.get("message", "QR 데이터 업로드 성공"),
                    "data": result
                }
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                return {
                    "success": False,
                    "error": error_data.get("error", f"HTTP {response.status_code}")
                }

        except requests.exceptions.Timeout:
            return {"success": False, "error": "업로드 시간 초과"}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "서버 연결 실패"}
        except Exception as e:
            return {"success": False, "error": f"업로드 오류: {str(e)}"}
