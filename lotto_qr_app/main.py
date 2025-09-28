"""
로또 용지 QR 인식 앱 - 메인 GUI
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
from PIL import Image, ImageTk
import os
import locale
import json
from typing import Optional, Dict, List

# macOS에서 한글 UI를 위한 로케일 설정
try:
    if os.name == 'posix':  # Unix/Linux/macOS
        locale.setlocale(locale.LC_ALL, 'ko_KR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'Korean_Korea.UTF-8')
    except:
        pass  # 로케일 설정 실패해도 계속 진행

from config import WINDOW_SIZE, SUPPORTED_FORMATS, WEB_APP_URL
from qr_processor import QRProcessor
from api_client import APIClient
from image_preprocessor import ImagePreprocessor


class LottoQRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("로또 용지 QR 인식기")
        self.root.geometry(WINDOW_SIZE)

        # 컴포넌트 초기화
        self.qr_processor = QRProcessor()
        self.api_client = APIClient()
        self.preprocessor = ImagePreprocessor()

        # 변수
        self.current_image_path = None
        self.qr_data = None
        self.parsed_lottery_data = None  # 파싱된 로또 번호 데이터

        # 설정 파일 경로
        self.settings_file = os.path.join(os.path.expanduser("~"), ".lotto_qr_settings.json")

        # 마지막 선택한 폴더 로드
        self.last_directory = self.load_last_directory()

        self.setup_ui()

    def setup_ui(self):
        """UI 구성"""
        # 메인 프레임
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 상단: 파일 선택 영역
        file_frame = ttk.LabelFrame(main_frame, text="이미지 파일 선택", padding="10")
        file_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        self.file_path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.file_path_var, width=60, state="readonly").grid(row=0, column=0, padx=(0, 5))
        ttk.Button(file_frame, text="파일 선택", command=self.select_file).grid(row=0, column=1)

        # 좌측: 이미지 미리보기
        image_frame = ttk.LabelFrame(main_frame, text="이미지 미리보기", padding="10")
        image_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))

        self.image_label = ttk.Label(image_frame, text="이미지를 선택하세요", anchor="center")
        self.image_label.grid(row=0, column=0)

        # 우측: 제어 및 결과 영역
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))

        # 제어 버튼들
        button_frame = ttk.LabelFrame(control_frame, text="처리", padding="10")
        button_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Button(button_frame, text="QR 인식", command=self.process_qr).grid(row=0, column=0, padx=(0, 5))

        # 연결 테스트
        test_frame = ttk.LabelFrame(control_frame, text="서버 연결", padding="10")
        test_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Button(test_frame, text="연결 테스트", command=self.test_connection).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(test_frame, text="데이터 업로드", command=self.upload_data).grid(row=0, column=1, padx=(5, 0))

        # 결과 표시 영역
        result_frame = ttk.LabelFrame(control_frame, text="처리 결과", padding="10")
        result_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 탭 위젯으로 결과 구분
        self.notebook = ttk.Notebook(result_frame)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # QR 결과 탭과 URL 접속 버튼
        qr_frame = ttk.Frame(self.notebook)
        self.notebook.add(qr_frame, text="QR 결과")

        # QR 텍스트 영역
        self.qr_text = scrolledtext.ScrolledText(qr_frame, height=10, width=40)
        self.qr_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        # QR 버튼 프레임
        qr_button_frame = ttk.Frame(qr_frame)
        qr_button_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=5, pady=(0, 5))

        ttk.Button(qr_button_frame, text="📋 QR 결과 복사", command=self.copy_qr_result).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(qr_button_frame, text="🔍 결과 상세보기", command=self.show_qr_details).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(qr_button_frame, text="🌐 URL 접속", command=self.open_qr_url).pack(side=tk.LEFT)

        qr_frame.grid_rowconfigure(0, weight=1)
        qr_frame.grid_columnconfigure(0, weight=1)

        # 로그 탭
        self.log_text = scrolledtext.ScrolledText(self.notebook, height=10, width=40)
        self.notebook.add(self.log_text, text="로그")

        # 하단: 상태바
        self.status_var = tk.StringVar()
        self.status_var.set("대기 중...")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))

        # 그리드 가중치 설정
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        control_frame.rowconfigure(2, weight=1)
        result_frame.rowconfigure(0, weight=1)

    def select_file(self):
        """파일 선택 대화상자"""
        file_path = filedialog.askopenfilename(
            title="로또 용지 이미지를 선택하세요",
            filetypes=SUPPORTED_FORMATS,
            initialdir=self.last_directory,  # 마지막 선택한 폴더부터 시작
            parent=self.root
        )

        if file_path:
            # 선택한 파일의 폴더 경로를 기억
            self.last_directory = os.path.dirname(file_path)
            self.save_last_directory()  # 설정 파일에 저장

            self.current_image_path = file_path
            self.file_path_var.set(file_path)
            self.display_image(file_path)
            self.log(f"파일 선택: {os.path.basename(file_path)}")
            self.log(f"폴더 기억: {self.last_directory}")

    def display_image(self, image_path: str):
        """이미지 미리보기 표시"""
        try:
            # 이미지 로드
            image = Image.open(image_path)

            # EXIF 방향 정보 처리
            image = self.fix_image_orientation(image)

            # 미리보기 크기로 조정 (비율 유지)
            display_size = (300, 400)
            image.thumbnail(display_size, Image.Resampling.LANCZOS)

            # tkinter용 이미지로 변환
            photo = ImageTk.PhotoImage(image)

            # 라벨에 표시
            self.image_label.configure(image=photo, text="")
            self.image_label.image = photo  # 참조 유지

        except Exception as e:
            self.log(f"이미지 표시 오류: {e}")
            messagebox.showerror("오류", f"이미지를 표시할 수 없습니다: {e}")

    def fix_image_orientation(self, image):
        """EXIF 방향 정보를 기반으로 이미지 회전 수정"""
        try:
            from PIL import Image

            # EXIF 데이터에서 방향 정보 추출
            exif = image.getexif()
            if exif:
                # ORIENTATION 태그 값은 274
                orientation = exif.get(274)
                if orientation == 2:
                    image = image.transpose(Image.FLIP_LEFT_RIGHT)
                elif orientation == 3:
                    image = image.rotate(180, expand=True)
                elif orientation == 4:
                    image = image.rotate(180, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
                elif orientation == 5:
                    image = image.rotate(-90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
                elif orientation == 6:
                    image = image.rotate(-90, expand=True)
                elif orientation == 7:
                    image = image.rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
                elif orientation == 8:
                    image = image.rotate(90, expand=True)

        except Exception as e:
            print(f"EXIF 방향 처리 오류: {e}")

        return image


    def copy_qr_result(self):
        """QR 결과를 클립보드에 복사"""
        try:
            text_content = self.qr_text.get(1.0, tk.END)
            self.root.clipboard_clear()
            self.root.clipboard_append(text_content.strip())
            self.log("QR 결과가 클립보드에 복사되었습니다")
            messagebox.showinfo("복사 완료", "QR 결과가 클립보드에 복사되었습니다")
        except Exception as e:
            self.log(f"QR 복사 오류: {e}")
            messagebox.showerror("오류", f"QR 복사 중 오류가 발생했습니다: {e}")

    def open_qr_url(self):
        """QR에서 추출된 URL을 웹 브라우저로 열기"""
        try:
            if not self.qr_data or not self.qr_data.get("success"):
                messagebox.showwarning("경고", "QR 데이터가 없습니다. 먼저 QR 코드를 인식하세요.")
                return

            # QR 데이터에서 URL 찾기
            urls = []

            # all_data에서 URL 패턴 찾기
            if "all_data" in self.qr_data:
                for qr_info in self.qr_data["all_data"]:
                    qr_text = str(qr_info)

                    # HTTP/HTTPS URL 패턴 찾기
                    import re
                    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
                    found_urls = re.findall(url_pattern, qr_text)
                    urls.extend(found_urls)

            if not urls:
                messagebox.showinfo("알림", "QR 코드에서 유효한 URL을 찾을 수 없습니다")
                return

            # 첫 번째 URL 사용
            url = urls[0]

            # 웹 브라우저로 열기
            import webbrowser
            webbrowser.open(url)

            self.log(f"URL 접속: {url}")
            messagebox.showinfo("접속 완료", f"웹 브라우저에서 URL을 열었습니다:\n{url}")

        except Exception as e:
            self.log(f"URL 접속 오류: {e}")
            messagebox.showerror("오류", f"URL 접속 중 오류가 발생했습니다: {e}")

    def process_qr(self):
        """QR 코드 처리"""
        if not self.current_image_path:
            messagebox.showwarning("경고", "먼저 이미지를 선택하세요.")
            return

        self.status_var.set("QR 코드 인식 중...")
        self.log("QR 코드 인식 시작...")

        threading.Thread(target=self._process_qr_thread, daemon=True).start()

    def _process_qr_thread(self):
        """QR 처리 스레드"""
        try:
            result = self.qr_processor.extract_qr_data(self.current_image_path)
            self.qr_data = result.get("data")

            self.root.after(0, self._update_qr_result, result)

        except Exception as e:
            self.root.after(0, self._handle_error, f"QR 처리 오류: {e}")

    def _update_qr_result(self, result: Dict):
        """QR 결과 UI 업데이트"""
        self.qr_text.delete(1.0, tk.END)

        if result["success"] and result["qr_count"] > 0:
            self.qr_text.insert(tk.END, f"✅ QR 코드 인식 성공\n")
            self.qr_text.insert(tk.END, f"인식된 QR 개수: {result['qr_count']}\n\n")

            if result["data"]:
                data = result["data"]
                self.qr_text.insert(tk.END, "추출된 정보:\n")
                if "round" in data:
                    self.qr_text.insert(tk.END, f"회차: {data['round']}\n")
                if "purchase_date" in data:
                    self.qr_text.insert(tk.END, f"구매일: {data['purchase_date']}\n")
                if "game_count" in data:
                    self.qr_text.insert(tk.END, f"게임 수: {data['game_count']}\n")
                self.qr_text.insert(tk.END, f"형식: {data.get('format', 'unknown')}\n")

            # 모든 QR 데이터 표시
            if result["all_data"]:
                self.qr_text.insert(tk.END, "\n모든 QR 데이터:\n")
                for i, qr_info in enumerate(result["all_data"]):
                    self.qr_text.insert(tk.END, f"QR {i+1}: {qr_info}\n")

            self.log(f"QR 완료: {result['qr_count']}개 인식")
        else:
            self.qr_text.insert(tk.END, "❌ QR 코드를 찾을 수 없습니다\n")
            if result.get("error"):
                self.qr_text.insert(tk.END, f"오류: {result['error']}\n")

        self.status_var.set("QR 처리 완료")

        # QR 데이터가 있으면 로또 번호 파싱 시도
        if result["success"] and result.get("all_data"):
            self._parse_lottery_numbers_from_qr(result["all_data"])


    def test_connection(self):
        """서버 연결 테스트"""
        self.status_var.set("서버 연결 테스트 중...")
        self.log("서버 연결 테스트...")

        threading.Thread(target=self._test_connection_thread, daemon=True).start()

    def _test_connection_thread(self):
        """연결 테스트 스레드"""
        try:
            result = self.api_client.test_connection()

            if result["success"]:
                message = f"✅ 서버 연결 성공\n서버: {WEB_APP_URL}"
                self.log("서버 연결 성공")
            else:
                message = f"❌ 서버 연결 실패\n오류: {result['error']}"
                self.log(f"서버 연결 실패: {result['error']}")

            self.root.after(0, lambda: messagebox.showinfo("연결 테스트", message))
            self.root.after(0, lambda: self.status_var.set("연결 테스트 완료"))

        except Exception as e:
            self.root.after(0, self._handle_error, f"연결 테스트 오류: {e}")

    def upload_data(self):
        """QR 데이터 업로드"""
        if not self.qr_data:
            messagebox.showwarning("경고", "먼저 QR 인식을 완료하세요.")
            return

        if not hasattr(self.qr_data, 'get') or not self.qr_data.get("url"):
            messagebox.showwarning("경고", "업로드할 QR 데이터가 없습니다.")
            return

        self.status_var.set("QR 데이터 업로드 중...")
        self.log("QR 데이터 업로드 시작...")

        threading.Thread(target=self._upload_data_thread, daemon=True).start()

    def _upload_data_thread(self):
        """업로드 스레드"""
        try:
            # QR 데이터를 사용하여 업로드
            qr_url = self.qr_data.get("url") if isinstance(self.qr_data, dict) else str(self.qr_data)

            # QR 업로드 API 사용
            result = self.api_client.upload_qr_data({
                "qr_url": qr_url,
                "confidence_score": 95.0
            })

            # 결과 처리
            if result["success"]:
                message = f"✅ QR 업로드 성공\n{result['message']}"
                self.log(f"QR 업로드 성공")
            else:
                message = f"❌ QR 업로드 실패\n{result['error']}"
                self.log(f"QR 업로드 실패: {result['error']}")

            self.root.after(0, lambda: messagebox.showinfo("업로드 결과", message))
            self.root.after(0, lambda: self.status_var.set("업로드 완료"))

        except Exception as e:
            self.root.after(0, self._handle_error, f"업로드 오류: {e}")

    def log(self, message: str):
        """로그 메시지 추가"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"

        self.log_text.insert(tk.END, log_message)
        self.log_text.see(tk.END)

    def load_last_directory(self) -> str:
        """마지막 선택한 디렉토리 로드"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    directory = settings.get('last_directory')
                    # 디렉토리가 존재하는지 확인
                    if directory and os.path.exists(directory):
                        return directory
        except Exception as e:
            print(f"설정 로드 오류: {e}")

        # 기본값 반환
        return os.path.expanduser("~/Desktop")

    def save_last_directory(self):
        """마지막 선택한 디렉토리 저장"""
        try:
            settings = {}
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)

            settings['last_directory'] = self.last_directory

            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"설정 저장 오류: {e}")

    def _parse_lottery_numbers_from_qr(self, qr_data_list):
        """QR 데이터에서 로또 번호 파싱"""
        try:
            self.parsed_lottery_data = None

            for qr_info in qr_data_list:
                if isinstance(qr_info, dict) and qr_info.get('format') == 'url':
                    url = qr_info.get('url') or qr_info.get('raw_data')
                    if url and 'dhlottery.co.kr' in url:
                        self.parsed_lottery_data = self._extract_numbers_from_url(url)
                        if self.parsed_lottery_data:
                            self.log(f"로또 번호 파싱 성공: {len(self.parsed_lottery_data.get('games', []))}게임")
                            break

        except Exception as e:
            self.log(f"번호 파싱 오류: {e}")

    def _extract_numbers_from_url(self, url):
        """URL에서 로또 번호 추출"""
        try:
            # URL에서 v 파라미터 추출
            import re
            from urllib.parse import urlparse, parse_qs

            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)

            if 'v' not in query_params:
                return None

            lottery_data = query_params['v'][0]

            # 데이터 파싱: {round}q{game1}q{game2}...
            parts = lottery_data.split('q')
            if len(parts) < 2:
                return None

            try:
                round_number = int(parts[0])
            except ValueError:
                return None

            games = []
            for i, game_data in enumerate(parts[1:], 1):
                if not game_data:
                    continue

                numbers = self._parse_game_numbers(game_data)
                if numbers and len(numbers) == 6:
                    games.append({
                        'game_index': i,
                        'numbers': sorted(numbers),
                        'raw_data': game_data
                    })

            if games:
                return {
                    'round': round_number,
                    'games': games,
                    'url': url
                }

        except Exception as e:
            self.log(f"URL 파싱 오류: {e}")

        return None

    def _parse_game_numbers(self, game_data):
        """게임 데이터에서 번호 추출"""
        try:
            numbers = []

            # 6개의 2자리 숫자 추출 시도
            if len(game_data) >= 12:
                for i in range(0, 12, 2):
                    num_str = game_data[i:i+2]
                    if num_str.isdigit():
                        num = int(num_str)
                        if 1 <= num <= 45 and num not in numbers:
                            numbers.append(num)

            # 정확히 6개를 찾았으면 반환
            if len(numbers) == 6:
                return numbers

            # 대체 방법: 모든 2자리 숫자 찾기
            numbers = []
            i = 0
            while i < len(game_data) - 1 and len(numbers) < 6:
                num_str = game_data[i:i+2]
                if num_str.isdigit():
                    num = int(num_str)
                    if 1 <= num <= 45 and num not in numbers:
                        numbers.append(num)
                        i += 2
                    else:
                        i += 1
                else:
                    i += 1

            return numbers if len(numbers) == 6 else None

        except Exception:
            return None

    def show_qr_details(self):
        """QR 결과 상세보기 창 표시"""
        if not self.qr_data or not self.parsed_lottery_data:
            messagebox.showwarning("경고", "먼저 QR 코드를 인식하세요.")
            return

        self._create_details_window()

    def _create_details_window(self):
        """상세보기 창 생성"""
        details_window = tk.Toplevel(self.root)
        details_window.title("QR 인식 결과 상세")
        details_window.geometry("600x500")
        details_window.resizable(True, True)

        # 메인 프레임
        main_frame = ttk.Frame(details_window, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 회차 정보
        info_frame = ttk.LabelFrame(main_frame, text="추첨 정보", padding="10")
        info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(info_frame, text=f"회차: {self.parsed_lottery_data['round']}회",
                 font=("", 12, "bold")).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(info_frame, text=f"게임 수: {len(self.parsed_lottery_data['games'])}게임",
                 font=("", 10)).grid(row=1, column=0, sticky=tk.W)

        # 번호 목록
        numbers_frame = ttk.LabelFrame(main_frame, text="인식된 번호", padding="10")
        numbers_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # 스크롤 가능한 프레임
        canvas = tk.Canvas(numbers_frame, height=250)
        scrollbar = ttk.Scrollbar(numbers_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # 각 게임의 번호 표시
        for i, game in enumerate(self.parsed_lottery_data['games']):
            game_frame = ttk.Frame(scrollable_frame)
            game_frame.grid(row=i, column=0, sticky=(tk.W, tk.E), pady=5, padx=5)

            # 게임 라벨
            ttk.Label(game_frame, text=f"게임 {game['game_index']}:",
                     font=("", 10, "bold")).grid(row=0, column=0, sticky=tk.W)

            # 번호 표시
            numbers_inner_frame = ttk.Frame(game_frame)
            numbers_inner_frame.grid(row=1, column=0, sticky=tk.W, pady=(5, 0))

            for j, num in enumerate(game['numbers']):
                # 번호 원형 라벨
                num_label = tk.Label(numbers_inner_frame, text=f"{num:02d}",
                                   bg=self._get_number_color(num), fg="white",
                                   font=("", 10, "bold"), width=3, height=1)
                num_label.grid(row=0, column=j, padx=2)

            # Raw 데이터 표시 (작은 글씨)
            ttk.Label(game_frame, text=f"원본: {game['raw_data']}",
                     font=("", 8), foreground="gray").grid(row=2, column=0, sticky=tk.W)

        canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # 버튼 프레임
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

        ttk.Button(button_frame, text="📋 번호 복사",
                  command=lambda: self._copy_lottery_numbers()).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="🌐 웹앱으로 전송",
                  command=lambda: self._send_to_webapp(details_window)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="닫기",
                  command=details_window.destroy).pack(side=tk.RIGHT)

        # 그리드 가중치 설정
        details_window.columnconfigure(0, weight=1)
        details_window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        numbers_frame.columnconfigure(0, weight=1)
        numbers_frame.rowconfigure(0, weight=1)

    def _get_number_color(self, num):
        """번호별 색상 반환"""
        if num <= 10:
            return "#FFA500"  # 주황
        elif num <= 20:
            return "#4169E1"  # 파랑
        elif num <= 30:
            return "#DC143C"  # 빨강
        elif num <= 40:
            return "#228B22"  # 초록
        else:
            return "#8A2BE2"  # 보라

    def _copy_lottery_numbers(self):
        """로또 번호를 클립보드에 복사"""
        if not self.parsed_lottery_data:
            return

        try:
            lines = []
            lines.append(f"🎰 {self.parsed_lottery_data['round']}회 로또 번호")
            lines.append("=" * 30)

            for game in self.parsed_lottery_data['games']:
                numbers_str = " ".join(f"{n:02d}" for n in game['numbers'])
                lines.append(f"게임 {game['game_index']}: {numbers_str}")

            result_text = "\n".join(lines)

            self.root.clipboard_clear()
            self.root.clipboard_append(result_text)
            messagebox.showinfo("복사 완료", "로또 번호가 클립보드에 복사되었습니다!")

        except Exception as e:
            messagebox.showerror("오류", f"복사 중 오류: {e}")

    def _send_to_webapp(self, parent_window):
        """웹앱으로 QR 데이터 전송"""
        if not self.parsed_lottery_data:
            messagebox.showwarning("경고", "전송할 데이터가 없습니다.")
            return

        try:
            # 기존 upload_data 메서드 사용
            parent_window.destroy()  # 상세창 닫기
            self.upload_data()

        except Exception as e:
            messagebox.showerror("오류", f"전송 중 오류: {e}")

    def _handle_error(self, error_message: str):
        """오류 처리"""
        self.log(error_message)
        messagebox.showerror("오류", error_message)
        self.status_var.set("오류 발생")


def main():
    """메인 함수"""
    root = tk.Tk()
    app = LottoQRApp(root)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
