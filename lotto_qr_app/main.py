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
from datetime import datetime

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
from database import QRDatabase


class LottoQRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("로또 용지 QR 인식기")
        self.root.geometry(WINDOW_SIZE)

        # 컴포넌트 초기화
        self.qr_processor = QRProcessor()
        self.api_client = APIClient(server_type="local")  # 기본값은 로컬 서버
        self.preprocessor = ImagePreprocessor()
        self.db = QRDatabase()  # 로컬 데이터베이스

        # 변수
        self.current_image_path = None
        self.qr_data = None
        self.parsed_lottery_data = None  # 파싱된 로또 번호 데이터
        self.current_scan_id = None  # 현재 스캔 ID

        # 설정 파일 경로
        self.settings_file = os.path.join(os.path.expanduser("~"), ".lotto_qr_settings.json")

        # 마지막 선택한 폴더 로드
        self.last_directory = self.load_last_directory()

        self.setup_ui()

        # 초기 로그 메시지
        self.log("로또 QR 인식 앱 시작")
        self.log(f"웹 앱 URL: {WEB_APP_URL}")

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

        # 서버 선택 영역
        server_frame = ttk.LabelFrame(control_frame, text="서버 선택", padding="10")
        server_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        # 서버 선택 드롭다운
        ttk.Label(server_frame, text="대상 서버:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.server_var = tk.StringVar()
        self.server_combo = ttk.Combobox(server_frame, textvariable=self.server_var,
                                        values=["로컬 서버 (127.0.0.1:5001)", "EC2 원격 서버 (43.201.26.3:8080)"],
                                        state="readonly", width=30)
        self.server_combo.set("로컬 서버 (127.0.0.1:5001)")  # 기본값
        self.server_combo.grid(row=0, column=1, padx=(0, 10))
        self.server_combo.bind('<<ComboboxSelected>>', self.on_server_change)

        # 서버 상태 표시
        self.server_status_var = tk.StringVar()
        self.server_status_var.set("로컬 서버 연결됨")
        self.server_status_label = ttk.Label(server_frame, textvariable=self.server_status_var, foreground="green")
        self.server_status_label.grid(row=1, column=0, columnspan=2, pady=(5, 0))

        # 로그인 영역
        login_frame = ttk.LabelFrame(control_frame, text="사용자 인증", padding="10")
        login_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        # 로그인 상태 표시
        self.login_status_var = tk.StringVar()
        self.login_status_var.set("로그인 필요")
        self.login_status_label = ttk.Label(login_frame, textvariable=self.login_status_var, foreground="red")
        self.login_status_label.grid(row=0, column=0, columnspan=4, pady=(0, 5))

        # 로그인 입력 필드
        ttk.Label(login_frame, text="사용자명:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5))
        self.username_var = tk.StringVar()
        self.username_entry = ttk.Entry(login_frame, textvariable=self.username_var, width=15)
        self.username_entry.grid(row=1, column=1, padx=(0, 10))

        ttk.Label(login_frame, text="비밀번호:").grid(row=1, column=2, sticky=tk.W, padx=(0, 5))
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(login_frame, textvariable=self.password_var, show="*", width=15)
        self.password_entry.grid(row=1, column=3, padx=(0, 5))

        # 로그인 버튼
        self.login_btn = ttk.Button(login_frame, text="로그인", command=self.handle_login)
        self.login_btn.grid(row=1, column=4, padx=(5, 0))

        # 로그아웃 버튼 (초기에는 숨김)
        self.logout_btn = ttk.Button(login_frame, text="로그아웃", command=self.handle_logout)
        self.logout_btn.grid(row=1, column=4, padx=(5, 0))
        self.logout_btn.grid_remove()  # 초기에는 숨김

        # 처리 및 서버 연결 버튼들
        button_frame = ttk.LabelFrame(control_frame, text="처리 및 서버", padding="10")
        button_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        # 모든 버튼을 한 줄로 배치
        ttk.Button(button_frame, text="QR 재인식", command=self.process_qr).grid(row=0, column=0, padx=(0, 5), sticky=tk.W)
        ttk.Button(button_frame, text="연결 테스트", command=self.test_connection).grid(row=0, column=1, padx=(0, 5), sticky=tk.W)
        ttk.Button(button_frame, text="데이터 업로드", command=self.upload_data).grid(row=0, column=2, padx=(0, 0), sticky=tk.W)

        # 결과 표시 영역
        result_frame = ttk.LabelFrame(control_frame, text="처리 결과", padding="10")
        result_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 탭 위젯으로 결과 구분
        self.notebook = ttk.Notebook(result_frame)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # QR 결과 탭과 URL 접속 버튼
        qr_frame = ttk.Frame(self.notebook)
        self.notebook.add(qr_frame, text="QR 결과")

        # QR 텍스트 영역
        self.qr_text = scrolledtext.ScrolledText(qr_frame, height=15, width=55)
        self.qr_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        # QR 버튼 프레임
        qr_button_frame = ttk.Frame(qr_frame)
        qr_button_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=5, pady=(0, 5))

        ttk.Button(qr_button_frame, text="📋 QR 결과 복사", command=self.copy_qr_result).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(qr_button_frame, text="📋 번호 복사", command=lambda: self._copy_lottery_numbers()).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(qr_button_frame, text="🌐 웹앱으로 전송", command=self.upload_data).pack(side=tk.LEFT, padx=(0, 5))

        qr_frame.grid_rowconfigure(0, weight=1)
        qr_frame.grid_columnconfigure(0, weight=1)

        # 로그 탭
        self.log_text = scrolledtext.ScrolledText(self.notebook, height=15, width=55)
        self.setup_log_context_menu()
        self.notebook.add(self.log_text, text="로그")

        # 데이터베이스 탭
        self.setup_database_tab()

        # 하단: 상태바
        self.status_var = tk.StringVar()
        self.status_var.set("대기 중...")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))

        # 그리드 가중치 설정
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        control_frame.rowconfigure(2, weight=1)  # 결과 영역이 row=2로 이동
        result_frame.rowconfigure(0, weight=1)

        # Enter 키 바인딩 (로그인 폼)
        self.password_entry.bind('<Return>', lambda e: self.handle_login())

    def setup_database_tab(self):
        """데이터베이스 관리 탭 설정"""
        db_frame = ttk.Frame(self.notebook)
        self.notebook.add(db_frame, text="데이터베이스")

        # 상단: 통계 정보
        stats_frame = ttk.LabelFrame(db_frame, text="데이터베이스 통계", padding="5")
        stats_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)

        self.stats_text = tk.Text(stats_frame, height=4, width=50)
        self.stats_text.grid(row=0, column=0, sticky=(tk.W, tk.E))

        # 중단: 회차 목록
        rounds_frame = ttk.LabelFrame(db_frame, text="저장된 회차 목록", padding="5")
        rounds_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        # 회차 목록을 위한 Treeview
        columns = ('round', 'scan_count', 'uploaded', 'last_scan')
        self.rounds_tree = ttk.Treeview(rounds_frame, columns=columns, show='headings', height=8)

        self.rounds_tree.heading('round', text='회차')
        self.rounds_tree.heading('scan_count', text='스캔 수')
        self.rounds_tree.heading('uploaded', text='업로드')
        self.rounds_tree.heading('last_scan', text='마지막 스캔')

        self.rounds_tree.column('round', width=80)
        self.rounds_tree.column('scan_count', width=80)
        self.rounds_tree.column('uploaded', width=80)
        self.rounds_tree.column('last_scan', width=150)

        self.rounds_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 스크롤바
        rounds_scrollbar = ttk.Scrollbar(rounds_frame, orient=tk.VERTICAL, command=self.rounds_tree.yview)
        rounds_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.rounds_tree.configure(yscrollcommand=rounds_scrollbar.set)

        # 회차 더블클릭 이벤트
        self.rounds_tree.bind('<Double-1>', self.on_round_double_click)

        # 하단: 버튼들
        button_frame = ttk.Frame(db_frame)
        button_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)

        ttk.Button(button_frame, text="새로고침", command=self.refresh_database_tab).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="회차 상세보기", command=self.show_round_details).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="선택 회차 삭제", command=self.delete_selected_round).pack(side=tk.LEFT, padx=(0, 5))

        # 그리드 가중치 설정
        db_frame.columnconfigure(0, weight=1)
        db_frame.rowconfigure(1, weight=1)
        stats_frame.columnconfigure(0, weight=1)
        rounds_frame.columnconfigure(0, weight=1)
        rounds_frame.rowconfigure(0, weight=1)

        # 초기 데이터 로드
        self.refresh_database_tab()

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

            # 파일 선택 후 자동으로 QR 인식 시작
            self.log("자동 QR 인식 시작...")
            self.auto_process_qr()

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

    def auto_process_qr(self):
        """파일 선택 후 자동 QR 코드 처리"""
        if not self.current_image_path:
            self.log("이미지 파일이 선택되지 않았습니다.")
            return

        self.status_var.set("QR 코드 자동 인식 중...")
        self.log("QR 코드 자동 인식 중...")

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
            #self.qr_text.insert(tk.END, f"인식된 QR 개수: {result['qr_count']}\n\n")

            self.log(f"QR 완료: {result['qr_count']}개 인식")
        else:
            self.qr_text.insert(tk.END, "❌ QR 코드를 찾을 수 없습니다\n")
            if result.get("error"):
                self.qr_text.insert(tk.END, f"오류: {result['error']}\n")

        self.status_var.set("QR 처리 완료")

        # QR 데이터가 있으면 로또 번호 파싱 시도
        if result["success"] and result.get("all_data"):
            self._parse_lottery_numbers_from_qr(result["all_data"])
            # 파싱된 결과를 바로 상세하게 표시
            self._display_detailed_qr_result_in_tab()
            # 데이터베이스에 저장
            self._save_to_database()


    def test_connection(self):
        """서버 연결 테스트"""
        self.status_var.set("서버 연결 테스트 중...")
        self.log(f"서버 연결 테스트 시작: {WEB_APP_URL}")

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
        """파싱된 로또 번호 데이터 업로드"""
        if not self.api_client.is_authenticated:
            messagebox.showwarning("인증 필요", "먼저 로그인해주세요.")
            return

        if not self.qr_data or not self.parsed_lottery_data:
            messagebox.showwarning("경고", "먼저 QR 인식을 완료하고 로또 번호가 파싱되어야 합니다.")
            return

        self.status_var.set("로또 번호 데이터 업로드 중...")
        self.log(f"로또 번호 데이터 업로드 시작: {WEB_APP_URL}")

        threading.Thread(target=self._upload_data_thread, daemon=True).start()

    def _upload_data_thread(self):
        """업로드 스레드 - 개별 게임 데이터 업로드"""
        try:
            # 업로드할 데이터 내용 로그 출력
            self.root.after(0, lambda: self.log("=" * 40))
            self.root.after(0, lambda: self.log("📤 업로드 데이터 내용:"))
            self.root.after(0, lambda: self.log(f"회차: {self.parsed_lottery_data['round']}"))
            self.root.after(0, lambda: self.log(f"게임 수: {len(self.parsed_lottery_data['games'])}게임"))

            # 로그인 상태 재확인
            if not self.api_client.is_authenticated:
                self.root.after(0, lambda: self.log("❌ 로그인 상태가 아닙니다"))
                return

            # 사용자 정보 확인
            user_info_result = self.api_client.get_user_info()
            self.root.after(0, lambda info=user_info_result: self.log(f"🔍 사용자 정보 확인: {info}"))

            if not user_info_result["success"]:
                self.root.after(0, lambda: self.log("❌ 사용자 정보 조회 실패 - 재로그인 필요"))
                # 인증 상태 초기화
                self.api_client.is_authenticated = False
                self.api_client.user_info = None
                self.root.after(0, lambda: self.update_login_ui())
                return

            # 각 게임을 개별적으로 업로드
            success_count = 0
            failed_count = 0
            duplicate_count = 0
            errors = []

            for i, game in enumerate(self.parsed_lottery_data['games'], 1):
                numbers_str = " ".join(f"{n:02d}" for n in game['numbers'])
                self.root.after(0, lambda i=i, numbers=numbers_str: self.log(f"게임 {i}: {numbers}"))

                # 웹앱 형식에 맞는 개별 게임 데이터 생성
                game_data = {
                    "numbers": game['numbers'],
                    "draw_number": self.parsed_lottery_data['round'],
                    "purchase_date": self.qr_data.get('purchase_date') or datetime.now().strftime('%Y-%m-%d')
                }

                # 개별 게임 업로드
                self.root.after(0, lambda data=game_data: self.log(f"📤 업로드 요청 데이터: {data}"))
                result = self.api_client.upload_purchase_data(game_data)
                self.root.after(0, lambda res=result: self.log(f"📨 서버 응답: {res}"))

                if result["success"]:
                    success_count += 1
                    self.root.after(0, lambda i=i: self.log(f"  ✅ 게임 {i} 업로드 성공"))
                else:
                    error_msg = result.get('error', '알 수 없는 오류')
                    error_details = result.get('details', '')

                    # 중복은 스킵으로 처리 (오류가 아님)
                    if error_msg == "중복 데이터":
                        duplicate_count += 1
                        self.root.after(0, lambda i=i, details=error_details: self.log(f"  ℹ️ 게임 {i} 스킵: 이미 등록된 번호입니다"))
                    else:
                        failed_count += 1
                        errors.append(f"게임 {i}: {error_msg}")
                        self.root.after(0, lambda i=i, err=error_msg: self.log(f"  ❌ 게임 {i} 업로드 실패: {err}"))

            self.root.after(0, lambda: self.log("=" * 40))

            # 전체 결과 정리
            total_games = len(self.parsed_lottery_data['games'])

            if success_count == total_games:
                # 모든 게임이 성공
                result = {
                    "success": True,
                    "message": f"✅ {success_count}개 게임이 모두 성공적으로 업로드되었습니다."
                }
            elif success_count > 0 and failed_count == 0:
                # 일부 성공, 나머지는 중복
                result = {
                    "success": True,
                    "message": f"✅ {success_count}개 게임 업로드 완료, {duplicate_count}개 게임은 이미 등록되어 스킵되었습니다."
                }
            elif success_count > 0 and failed_count > 0:
                # 성공, 실패, 중복 혼재
                message_parts = [f"✅ {success_count}개 게임 업로드 완료"]
                if duplicate_count > 0:
                    message_parts.append(f"ℹ️ {duplicate_count}개 게임 스킵(중복)")
                if failed_count > 0:
                    message_parts.append(f"❌ {failed_count}개 게임 실패")
                    message_parts.append(f"실패 원인: {'; '.join(errors[:3])}")

                result = {
                    "success": True,
                    "message": "\n".join(message_parts)
                }
            elif duplicate_count == total_games:
                # 모든 게임이 중복
                result = {
                    "success": True,
                    "message": f"ℹ️ 모든 게임({duplicate_count}개)이 이미 등록되어 있어 스킵되었습니다."
                }
            elif failed_count > 0 and duplicate_count > 0:
                # 실패와 중복만 있음
                result = {
                    "success": False,
                    "error": f"❌ {failed_count}개 게임 실패, {duplicate_count}개 게임 스킵(중복)\n실패 원인: {'; '.join(errors[:3])}"
                }
            else:
                # 모든 게임이 실패
                result = {
                    "success": False,
                    "error": f"❌ 모든 게임({failed_count}개) 업로드 실패\n원인: {'; '.join(errors[:3])}"
                }

            # 결과 처리
            if result["success"]:
                message_data = result.get('data', {})
                saved_count = message_data.get('saved_count', 0)
                duplicate_count = message_data.get('duplicate_count', 0)
                total_parsed = message_data.get('parsed_games', 0)

                message = result.get('message', '업로드 완료')

                self.root.after(0, lambda msg=message: self.log(f"✅ {msg}"))

                # 데이터베이스에 업로드 상태 저장
                if self.current_scan_id:
                    self.db.save_upload_status(self.current_scan_id, True, message)
                    self.refresh_database_tab()

            else:
                error_msg = result.get('error', '알 수 없는 오류')
                error_details = result.get('details', '')

                message = f"❌ 업로드 실패: {error_msg}"
                if error_details:
                    message += f"\n상세: {error_details}"

                self.root.after(0, lambda msg=error_msg: self.log(f"❌ 업로드 실패: {msg}"))

                # 데이터베이스에 업로드 실패 상태 저장
                if self.current_scan_id:
                    self.db.save_upload_status(self.current_scan_id, False, error_msg)
                    self.refresh_database_tab()

            self.root.after(0, lambda msg=message: messagebox.showinfo("업로드 결과", msg))
            self.root.after(0, lambda: self.status_var.set("업로드 완료"))

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            self.root.after(0, lambda: self.log(f"❌ 업로드 예외 발생: {e}"))
            self.root.after(0, lambda: self.log(f"🔍 상세 오류:\n{error_detail}"))
            self.root.after(0, self._handle_error, f"업로드 오류: {e}")

    def log(self, message: str):
        """로그 메시지 추가"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"

        self.log_text.insert(tk.END, log_message)
        self.log_text.see(tk.END)

    def setup_log_context_menu(self):
        """로그 텍스트 위젯의 컨텍스트 메뉴 설정"""
        # 컨텍스트 메뉴 생성
        self.log_context_menu = tk.Menu(self.root, tearoff=0)
        self.log_context_menu.add_command(label="전체 선택 (Ctrl+A)", command=self.select_all_log)
        self.log_context_menu.add_command(label="복사 (Ctrl+C)", command=self.copy_log_selection)
        self.log_context_menu.add_separator()
        self.log_context_menu.add_command(label="모든 로그 복사", command=self.copy_all_log)
        self.log_context_menu.add_command(label="로그 지우기", command=self.clear_log)

        # 우클릭 이벤트 바인딩
        self.log_text.bind("<Button-3>", self.show_log_context_menu)  # 우클릭 (macOS/Linux)
        self.log_text.bind("<Button-2>", self.show_log_context_menu)  # 중간 클릭 (일부 시스템)

        # 키보드 단축키 바인딩
        self.log_text.bind("<Control-a>", lambda e: self.select_all_log())
        self.log_text.bind("<Control-A>", lambda e: self.select_all_log())
        self.log_text.bind("<Command-a>", lambda e: self.select_all_log())  # macOS
        self.log_text.bind("<Control-c>", lambda e: self.copy_log_selection())
        self.log_text.bind("<Control-C>", lambda e: self.copy_log_selection())
        self.log_text.bind("<Command-c>", lambda e: self.copy_log_selection())  # macOS

    def show_log_context_menu(self, event):
        """로그 컨텍스트 메뉴 표시"""
        try:
            # 선택된 텍스트가 있는지 확인하여 메뉴 항목 활성화/비활성화
            try:
                selected_text = self.log_text.get(tk.SEL_FIRST, tk.SEL_LAST)
                has_selection = bool(selected_text)
            except tk.TclError:
                has_selection = False

            # 복사 메뉴 상태 설정
            if has_selection:
                self.log_context_menu.entryconfig("복사 (Ctrl+C)", state="normal")
            else:
                self.log_context_menu.entryconfig("복사 (Ctrl+C)", state="disabled")

            # 컨텍스트 메뉴 표시
            self.log_context_menu.post(event.x_root, event.y_root)
        except Exception as e:
            print(f"컨텍스트 메뉴 표시 오류: {e}")

    def select_all_log(self):
        """로그 텍스트 전체 선택"""
        try:
            self.log_text.tag_add(tk.SEL, "1.0", tk.END)
            self.log_text.mark_set(tk.INSERT, "1.0")
            self.log_text.see(tk.INSERT)
            return "break"  # 기본 이벤트 처리 중단
        except Exception as e:
            print(f"전체 선택 오류: {e}")

    def copy_log_selection(self):
        """선택된 로그 텍스트 복사"""
        try:
            try:
                selected_text = self.log_text.get(tk.SEL_FIRST, tk.SEL_LAST)
                if selected_text:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(selected_text)
                    self.log("📋 선택된 로그를 클립보드에 복사했습니다.")
                else:
                    self.log("⚠️ 복사할 텍스트가 선택되지 않았습니다.")
            except tk.TclError:
                self.log("⚠️ 복사할 텍스트가 선택되지 않았습니다.")
            return "break"
        except Exception as e:
            print(f"복사 오류: {e}")

    def copy_all_log(self):
        """모든 로그 텍스트 복사"""
        try:
            all_text = self.log_text.get("1.0", tk.END)
            if all_text.strip():
                self.root.clipboard_clear()
                self.root.clipboard_append(all_text)
                self.log("📋 모든 로그를 클립보드에 복사했습니다.")
            else:
                self.log("⚠️ 복사할 로그가 없습니다.")
        except Exception as e:
            print(f"전체 복사 오류: {e}")

    def clear_log(self):
        """로그 지우기"""
        try:
            if messagebox.askyesno("로그 지우기", "모든 로그를 지우시겠습니까?"):
                self.log_text.delete("1.0", tk.END)
                self.log("🗑️ 로그가 지워졌습니다.")
        except Exception as e:
            print(f"로그 지우기 오류: {e}")

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

    def _display_detailed_qr_result_in_tab(self):
        """QR 탭에 상세한 QR 결과 표시 (상세보기 창 내용을 그대로 표시)"""
        if not self.parsed_lottery_data:
            self.log("파싱된 로또 데이터가 없습니다")
            return

        self.log(f"로또 번호 상세 표시 시작: {len(self.parsed_lottery_data['games'])}게임")

        try:
            # 추첨 정보 섹션
            #self.qr_text.insert(tk.END, "🎰 추첨 정보:\n")
            self.qr_text.insert(tk.END, "─" * 40 + "\n")
            self.qr_text.insert(tk.END, f"회차: {self.parsed_lottery_data['round']}회  게임수 : {len(self.parsed_lottery_data['games'])}게임\n")
            #   self.qr_text.insert(tk.END, f"게임 수: {len(self.parsed_lottery_data['games'])}게임\n")

            # 인식된 번호 섹션
            #self.qr_text.insert(tk.END, "🔢 인식된 번호:\n")
            self.qr_text.insert(tk.END, "-" * 40 + "\n")

            for game in self.parsed_lottery_data['games']:
                numbers = game['numbers']
                game_index = game['game_index']

                # 게임 번호 표시
                self.qr_text.insert(tk.END, f"게임 {game_index}:  ", "game_header")

                # 번호를 색상별로 구분해서 표시 (더 큰 폰트)
                self.qr_text.insert(tk.END, "  ")
                for i, num in enumerate(numbers):
                    if i > 0:
                        self.qr_text.insert(tk.END, "  ")

                    # 번호에 따른 색상 태그 설정
                    color_tag = self._get_number_tag(num)
                    self.qr_text.insert(tk.END, f"{num:02d}", color_tag)

                self.qr_text.insert(tk.END, "\n")

                # 원본 데이터 (작은 글씨로)
                #self.qr_text.insert(tk.END, f"  └ 원본: {game['raw_data']}\n\n", "raw_data")

            # 색상 태그 설정
            self._setup_number_color_tags()

            # 게임 헤더와 원본 데이터 스타일 설정
            self.qr_text.tag_configure("game_header", font=("", 11, "bold"))
            self.qr_text.tag_configure("raw_data", font=("", 8), foreground="gray")

        except Exception as e:
            self.log(f"상세 결과 표시 오류: {e}")

    def _display_parsed_numbers_in_qr_tab(self):
        """QR 탭에 파싱된 로또 번호 표시 (기존 메서드 - 호환성 유지)"""
        # 이제 상세보기 메서드를 호출
        self._display_detailed_qr_result_in_tab()

    def _get_number_tag(self, num):
        """번호별 색상 태그명 반환"""
        if num <= 10:
            return "orange_num"
        elif num <= 20:
            return "blue_num"
        elif num <= 30:
            return "red_num"
        elif num <= 40:
            return "green_num"
        else:
            return "purple_num"

    def _setup_number_color_tags(self):
        """QR 텍스트 위젯에 색상 태그 설정"""
        try:
            # 색상 태그 구성 (더 큰 폰트로 변경)
            self.qr_text.tag_configure("orange_num", foreground="#FF6600", font=("", 12, "bold"))
            self.qr_text.tag_configure("blue_num", foreground="#0066FF", font=("", 12, "bold"))
            self.qr_text.tag_configure("red_num", foreground="#CC0000", font=("", 12, "bold"))
            self.qr_text.tag_configure("green_num", foreground="#006600", font=("", 12, "bold"))
            self.qr_text.tag_configure("purple_num", foreground="#6600CC", font=("", 12, "bold"))
        except Exception as e:
            self.log(f"색상 태그 설정 오류: {e}")

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

    def _save_to_database(self):
        """QR 데이터를 데이터베이스에 저장"""
        try:
            if self.qr_data and self.parsed_lottery_data:
                # 중복 확인
                duplicate_scan = self.db.check_duplicate_scan(
                    qr_data=self.qr_data,
                    parsed_lottery_data=self.parsed_lottery_data
                )

                if duplicate_scan:
                    # 이미 존재하는 경우 로그만 남기고 저장하지 않음
                    self.current_scan_id = duplicate_scan['scan_id']
                    round_number = self.parsed_lottery_data.get('round', '알 수 없음')
                    scan_date = duplicate_scan['scan_date']
                    self.log(f"⚠️ {round_number}회차 동일 용지 이미 존재 (스캔 ID: {self.current_scan_id}, 날짜: {scan_date})")
                    self.log("새로 저장하지 않고 기존 데이터를 사용합니다")
                else:
                    # 새로 저장
                    scan_id = self.db.save_qr_scan(
                        qr_data=self.qr_data,
                        parsed_lottery_data=self.parsed_lottery_data,
                        image_path=self.current_image_path
                    )
                    self.current_scan_id = scan_id
                    round_number = self.parsed_lottery_data.get('round', '알 수 없음')
                    self.log(f"✅ {round_number}회차 새 용지 데이터베이스에 저장 완료 (ID: {scan_id})")

                # 데이터베이스 탭 새로고침
                self.refresh_database_tab()
        except Exception as e:
            self.log(f"데이터베이스 저장 오류: {e}")

    def refresh_database_tab(self):
        """데이터베이스 탭 새로고침"""
        try:
            # 통계 정보 업데이트
            stats = self.db.get_statistics()
            stats_text = f"""총 스캔: {stats['total_scans']}개
저장된 회차: {stats['total_rounds']}회차
총 게임: {stats['total_games']}게임
업로드 성공: {stats['successful_uploads']}개"""

            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(tk.END, stats_text)

            # 회차 목록 업데이트
            for item in self.rounds_tree.get_children():
                self.rounds_tree.delete(item)

            rounds = self.db.get_all_rounds()
            for round_data in rounds:
                upload_status = f"{round_data['uploaded_count']}/{round_data['scan_count']}"
                last_scan = round_data['last_scan'][:16] if round_data['last_scan'] else ""

                self.rounds_tree.insert('', 'end', values=(
                    round_data['round_number'],
                    round_data['scan_count'],
                    upload_status,
                    last_scan
                ))

        except Exception as e:
            self.log(f"데이터베이스 탭 새로고침 오류: {e}")

    def on_round_double_click(self, event):
        """회차 더블클릭 이벤트"""
        self.show_round_details()

    def show_round_details(self):
        """선택된 회차의 상세 정보 표시"""
        selection = self.rounds_tree.selection()
        if not selection:
            messagebox.showwarning("경고", "회차를 선택해주세요.")
            return

        item = self.rounds_tree.item(selection[0])
        round_number = item['values'][0]

        try:
            details = self.db.get_round_details(round_number)
            self._create_round_details_window(details)
        except Exception as e:
            messagebox.showerror("오류", f"회차 상세 정보 조회 실패: {e}")

    def _create_round_details_window(self, details):
        """회차 상세 정보 창 생성"""
        details_window = tk.Toplevel(self.root)
        details_window.title(f"{details['round_number']}회차 상세 정보")
        details_window.geometry("700x500")
        details_window.resizable(True, True)

        # 메인 프레임
        main_frame = ttk.Frame(details_window, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 회차 정보
        info_frame = ttk.LabelFrame(main_frame, text="회차 정보", padding="10")
        info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(info_frame, text=f"회차: {details['round_number']}회",
                 font=("", 12, "bold")).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(info_frame, text=f"총 스캔: {details['total_scans']}회",
                 font=("", 10)).grid(row=1, column=0, sticky=tk.W)
        ttk.Label(info_frame, text=f"총 게임: {details['total_games']}게임",
                 font=("", 10)).grid(row=2, column=0, sticky=tk.W)

        # 스캔 목록
        scans_frame = ttk.LabelFrame(main_frame, text="스캔 목록", padding="10")
        scans_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # 스크롤 가능한 텍스트 영역
        scans_text = scrolledtext.ScrolledText(scans_frame, height=20, width=70)
        scans_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 스캔 정보 표시
        for i, scan in enumerate(details['scans'], 1):
            scans_text.insert(tk.END, f"스캔 {i}: {scan['scan_date']}\n", "scan_header")
            scans_text.insert(tk.END, f"형식: {scan['qr_format']}, 신뢰도: {scan['confidence_score']:.2f}\n")

            for game in scan['games']:
                numbers_str = " ".join(f"{n:02d}" for n in game['numbers'])
                scans_text.insert(tk.END, f"  게임 {game['game_index']}: {numbers_str}\n", "numbers")

            if scan['upload_status']:
                status = "✅ 업로드됨" if scan['upload_status']['uploaded'] else "❌ 업로드 안됨"
                scans_text.insert(tk.END, f"  업로드 상태: {status}\n", "upload_status")

            scans_text.insert(tk.END, "\n")

        # 텍스트 스타일 설정
        scans_text.tag_configure("scan_header", font=("", 10, "bold"))
        scans_text.tag_configure("numbers", foreground="blue", font=("", 10, "bold"))
        scans_text.tag_configure("upload_status", foreground="green")

        # 버튼 프레임
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

        ttk.Button(button_frame, text="닫기", command=details_window.destroy).pack(side=tk.RIGHT)

        # 그리드 가중치 설정
        details_window.columnconfigure(0, weight=1)
        details_window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        scans_frame.columnconfigure(0, weight=1)
        scans_frame.rowconfigure(0, weight=1)

    def delete_selected_round(self):
        """선택된 회차 삭제"""
        selection = self.rounds_tree.selection()
        if not selection:
            messagebox.showwarning("경고", "삭제할 회차를 선택해주세요.")
            return

        item = self.rounds_tree.item(selection[0])
        round_number = item['values'][0]

        if messagebox.askyesno("확인", f"{round_number}회차의 모든 데이터를 삭제하시겠습니까?"):
            try:
                deleted_count = self.db.delete_round_data(round_number)
                self.log(f"{round_number}회차 데이터 삭제 완료 ({deleted_count}개 스캔)")
                self.refresh_database_tab()
                messagebox.showinfo("완료", f"{round_number}회차 데이터가 삭제되었습니다.")
            except Exception as e:
                messagebox.showerror("오류", f"데이터 삭제 실패: {e}")

    def _handle_error(self, error_message: str):
        """오류 처리"""
        self.log(error_message)
        messagebox.showerror("오류", error_message)
        self.status_var.set("오류 발생")

    def on_server_change(self, event=None):
        """서버 변경 이벤트 핸들러"""
        selected = self.server_var.get()

        if "로컬 서버" in selected:
            server_type = "local"
        elif "EC2 원격 서버" in selected:
            server_type = "remote"
        else:
            return

        # API 클라이언트 서버 전환
        result = self.api_client.switch_server(server_type)

        if result["success"]:
            self.server_status_var.set(f"{result['server_info']['name']} 연결됨")
            self.server_status_label.config(foreground="green")
            self.log(f"서버가 {result['server_info']['name']}로 전환되었습니다.")

            # 서버 전환시 로그인 상태 초기화
            self.login_status_var.set("로그인 필요")
            self.login_status_label.config(foreground="red")
            self.login_btn.grid()
            self.logout_btn.grid_remove()

            # 연결 테스트 자동 실행
            self.test_connection()
        else:
            self.server_status_var.set(f"서버 전환 실패: {result['error']}")
            self.server_status_label.config(foreground="red")
            self.log(f"서버 전환 실패: {result['error']}")

    def handle_login(self):
        """로그인 처리"""
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()

        if not username or not password:
            messagebox.showwarning("입력 오류", "사용자명과 비밀번호를 모두 입력해주세요.")
            return

        self.status_var.set("로그인 중...")
        self.log(f"사용자 '{username}'로 로그인 시도 중...")

        def _login_thread():
            try:
                result = self.api_client.login(username, password)

                # UI 업데이트는 메인 스레드에서
                self.root.after(0, lambda: self._handle_login_result(result))
            except Exception as e:
                error_msg = f"로그인 중 오류: {str(e)}"
                self.root.after(0, lambda: self._handle_login_error(error_msg))

        threading.Thread(target=_login_thread, daemon=True).start()

    def _handle_login_result(self, result):
        """로그인 결과 처리 (메인 스레드)"""
        if result["success"]:
            user_info = result.get("user_info", {})
            username = user_info.get("username", "사용자")

            self.login_status_var.set(f"✅ {username}님 로그인됨")
            self.login_status_label.configure(foreground="green")

            # 로그인 폼 숨기고 로그아웃 버튼 표시
            self.username_entry.grid_remove()
            self.password_entry.grid_remove()
            ttk.Label(self.username_entry.master, text="사용자명:").grid_remove()
            ttk.Label(self.password_entry.master, text="비밀번호:").grid_remove()
            self.login_btn.grid_remove()
            self.logout_btn.grid()

            # 비밀번호 필드 초기화
            self.password_var.set("")

            self.log(f"✅ {result['message']}")
            self.status_var.set("로그인 완료")
        else:
            error_msg = result.get("details", result.get("error", "로그인 실패"))
            self.log(f"❌ 로그인 실패: {error_msg}")
            messagebox.showerror("로그인 실패", error_msg)
            self.status_var.set("로그인 실패")

    def _handle_login_error(self, error_msg):
        """로그인 오류 처리 (메인 스레드)"""
        self.log(error_msg)
        messagebox.showerror("로그인 오류", error_msg)
        self.status_var.set("로그인 오류")

    def handle_logout(self):
        """로그아웃 처리"""
        self.status_var.set("로그아웃 중...")
        self.log("로그아웃 중...")

        def _logout_thread():
            try:
                result = self.api_client.logout()
                self.root.after(0, lambda: self._handle_logout_result(result))
            except Exception as e:
                error_msg = f"로그아웃 중 오류: {str(e)}"
                self.root.after(0, lambda: self.log(error_msg))

        threading.Thread(target=_logout_thread, daemon=True).start()

    def _handle_logout_result(self, result):
        """로그아웃 결과 처리 (메인 스레드)"""
        self.login_status_var.set("로그인 필요")
        self.login_status_label.configure(foreground="red")

        # 로그아웃 버튼 숨기고 로그인 폼 다시 표시
        self.logout_btn.grid_remove()

        # 라벨들 다시 표시
        ttk.Label(self.username_entry.master, text="사용자명:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(self.password_entry.master, text="비밀번호:").grid(row=1, column=2, sticky=tk.W, padx=(0, 5))

        self.username_entry.grid()
        self.password_entry.grid()
        self.login_btn.grid()

        # 입력 필드 초기화
        self.username_var.set("")
        self.password_var.set("")

        self.log("✅ 로그아웃되었습니다")
        self.status_var.set("로그아웃 완료")

    def update_login_ui(self):
        """로그인 상태에 따른 UI 업데이트"""
        if self.api_client.is_authenticated:
            username = self.api_client.user_info.get("username", "사용자") if self.api_client.user_info else "사용자"
            self.login_status_var.set(f"✅ {username}님 로그인됨")
            self.login_status_label.configure(foreground="green")
        else:
            self.login_status_var.set("로그인 필요")
            self.login_status_label.configure(foreground="red")


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
