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

        # 인증 상태
        self.is_authenticated = False
        self.user_info = None

        if api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {api_key}'
            })

    def login(self, username: str, password: str) -> Dict:
        """
        웹 앱에 로그인
        """
        try:
            login_url = f"{WEB_APP_URL}/login"

            # 로그인 페이지에서 CSRF 토큰 가져오기
            resp = self.session.get(login_url, timeout=10)
            if resp.status_code != 200:
                return {
                    "success": False,
                    "error": "로그인 페이지 접근 실패",
                    "details": f"HTTP {resp.status_code}"
                }

            # CSRF 토큰 추출 (BeautifulSoup 사용하지 않고 간단하게)
            csrf_token = None
            if 'csrf_token' in resp.text:
                import re
                csrf_match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', resp.text)
                if csrf_match:
                    csrf_token = csrf_match.group(1)

            # 로그인 데이터 준비
            login_data = {
                'username': username,
                'password': password
            }
            if csrf_token:
                login_data['csrf_token'] = csrf_token

            # 로그인 요청
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': login_url
            }

            resp = self.session.post(login_url, data=login_data, headers=headers, timeout=10, allow_redirects=False)

            # 로그인 성공 확인 - 다중 검증 방식

            # 1. 응답 내용 확인 (로그인 실패 메시지 체크)
            response_text = resp.text.lower()
            if any(error_text in response_text for error_text in [
                '잘못된', '실패', 'invalid', 'failed', '오류', 'error',
                '비밀번호', 'password', '사용자', 'username'
            ]):
                return {
                    "success": False,
                    "error": "로그인 실패",
                    "details": "사용자명 또는 비밀번호가 올바르지 않습니다."
                }

            # 2. 사용자 정보 조회로 실제 로그인 여부 확인
            user_info = self.get_user_info()

            if user_info["success"]:
                # 로그인 성공
                self.is_authenticated = True
                self.user_info = user_info["data"]
                return {
                    "success": True,
                    "message": f"{self.user_info.get('username')}님으로 로그인되었습니다.",
                    "user_info": self.user_info
                }
            else:
                # 로그인 실패 - 사용자 정보 조회 실패는 인증 실패를 의미
                error_msg = user_info.get("error", "로그인 실패")
                if "인증" in error_msg or "로그인" in error_msg:
                    return {
                        "success": False,
                        "error": "로그인 실패",
                        "details": "사용자명 또는 비밀번호가 올바르지 않습니다."
                    }
                else:
                    return {
                        "success": False,
                        "error": "로그인 후 사용자 정보 조회 실패",
                        "details": error_msg
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
                "error": "로그인 시간 초과"
            }
        except Exception as e:
            return {
                "success": False,
                "error": "로그인 오류",
                "details": str(e)
            }

    def get_user_info(self) -> Dict:
        """
        현재 로그인된 사용자 정보 조회
        """
        try:
            user_url = f"{WEB_APP_URL}/api/user/info"
            resp = self.session.get(user_url, timeout=10)

            if resp.status_code == 200:
                user_data = resp.json()
                return {
                    "success": True,
                    "data": user_data
                }
            elif resp.status_code == 401:
                return {
                    "success": False,
                    "error": "인증 필요",
                    "details": "로그인이 필요합니다."
                }
            else:
                return {
                    "success": False,
                    "error": f"사용자 정보 조회 실패 (HTTP {resp.status_code})"
                }

        except Exception as e:
            return {
                "success": False,
                "error": "사용자 정보 조회 오류",
                "details": str(e)
            }

    def logout(self) -> Dict:
        """
        로그아웃
        """
        try:
            logout_url = f"{WEB_APP_URL}/logout"
            resp = self.session.post(logout_url, timeout=10)

            self.is_authenticated = False
            self.user_info = None

            return {
                "success": True,
                "message": "로그아웃되었습니다."
            }

        except Exception as e:
            self.is_authenticated = False
            self.user_info = None
            return {
                "success": True,
                "message": "로그아웃되었습니다.",
                "details": f"서버 연결 오류: {str(e)}"
            }

    def upload_purchase_data(self, purchase_data: Dict) -> Dict:
        """
        구매 데이터를 웹 앱에 업로드
        """
        try:
            # 로그인 상태 확인
            if not self.is_authenticated:
                return {
                    "success": False,
                    "error": "인증 필요",
                    "details": "먼저 로그인해주세요."
                }

            # 데이터 검증
            validation_result = self._validate_purchase_data(purchase_data)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": "데이터 검증 실패",
                    "details": validation_result["errors"]
                }

            # 개별 게임 업로드는 기존 API 사용
            response = self.session.post(API_ENDPOINT, json=purchase_data, timeout=30)

            if response.status_code in [200, 201]:
                return {
                    "success": True,
                    "data": response.json(),
                    "message": "구매 데이터가 성공적으로 업로드되었습니다."
                }
            elif response.status_code == 400:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                error_msg = error_data.get("error", "잘못된 요청")
                error_details = error_data.get("details", "")

                return {
                    "success": False,
                    "error": "데이터 검증 실패",
                    "details": error_details or error_msg
                }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "error": "인증 실패",
                    "details": "API 키를 확인해주세요."
                }
            elif response.status_code == 409:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                return {
                    "success": False,
                    "error": "중복 데이터",
                    "details": error_data.get("details", "이미 등록된 구매 데이터입니다.")
                }
            else:
                return {
                    "success": False,
                    "error": f"서버 오류 ({response.status_code})",
                    "details": response.text
                }

        except requests.exceptions.ConnectionError as e:
            return {
                "success": False,
                "error": "연결 실패",
                "details": f"웹 앱 서버({WEB_APP_URL})에 연결할 수 없습니다. 상세: {str(e)}"
            }
        except requests.exceptions.Timeout as e:
            return {
                "success": False,
                "error": "요청 시간 초과",
                "details": f"서버 응답 시간이 초과되었습니다. 상세: {str(e)}"
            }
        except Exception as e:
            import traceback
            return {
                "success": False,
                "error": "예상치 못한 오류",
                "details": f"오류: {str(e)}\n상세: {traceback.format_exc()}"
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

        # 개별 게임 데이터와 배치 게임 데이터 모두 지원
        if "games" in data:
            # 배치 게임 데이터 형식 (기존)
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

        elif "numbers" in data:
            # 개별 게임 데이터 형식 (QR 앱용)
            numbers = data.get("numbers", [])
            if not numbers:
                errors.append("번호가 없습니다.")
            elif len(numbers) != 6:
                errors.append(f"번호는 6개여야 합니다. (현재: {len(numbers)}개)")
            else:
                # 번호 범위 확인
                for num in numbers:
                    if not isinstance(num, int) or not (1 <= num <= 45):
                        errors.append(f"잘못된 번호 {num}")

                # 중복 번호 확인
                if len(set(numbers)) != len(numbers):
                    errors.append("중복 번호가 있습니다.")

            # 회차 번호 확인
            if "draw_number" not in data:
                errors.append("필수 필드 누락: draw_number")
        elif "qr_url" in data:
            # QR URL 데이터 형식
            qr_url = data.get("qr_url", "")
            if not qr_url:
                errors.append("QR URL이 필요합니다.")
            elif not qr_url.startswith("http"):
                errors.append("유효한 QR URL이 아닙니다.")
            # QR URL이 있으면 다른 필드 검증 생략
            return {
                "valid": len(errors) == 0,
                "errors": errors
            }
        else:
            errors.append("필수 필드 누락: games, numbers 또는 qr_url")

        # 회차 검증 (round 또는 draw_number) - QR URL 형식이 아닌 경우만
        round_num = data.get("round") or data.get("draw_number")
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

    def create_qr_upload_data(self, qr_url: str, confidence_score: float = 95.0) -> Dict:
        """
        QR 업로드용 데이터 객체 생성
        """
        return {
            "qr_url": qr_url,
            "confidence_score": confidence_score,
            "source": "qr_app",
            "timestamp": datetime.now().isoformat()
        }

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
            url = f"{WEB_APP_URL}/api/purchases/qr"
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
