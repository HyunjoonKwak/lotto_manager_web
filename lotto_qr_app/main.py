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
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 한글 폰트 설정 (macOS)
def setup_korean_font():
    """한글 폰트 설정 for matplotlib"""
    try:
        # macOS 시스템 폰트 경로
        font_candidates = [
            '/System/Library/Fonts/Supplemental/AppleGothic.ttf',  # AppleGothic
            '/System/Library/Fonts/AppleSDGothicNeo.ttc',  # Apple SD Gothic Neo
            '/Library/Fonts/Arial Unicode.ttf',  # Arial Unicode MS
        ]

        for font_path in font_candidates:
            if os.path.exists(font_path):
                font_prop = fm.FontProperties(fname=font_path)
                plt.rc('font', family=font_prop.get_name())
                plt.rc('axes', unicode_minus=False)  # 마이너스 기호 깨짐 방지
                return True

        # 폰트를 찾지 못한 경우 시스템 폰트 목록에서 찾기
        font_list = [f.name for f in fm.fontManager.ttflist if 'gothic' in f.name.lower() or 'malgun' in f.name.lower()]
        if font_list:
            plt.rc('font', family=font_list[0])
            plt.rc('axes', unicode_minus=False)
            return True

    except Exception as e:
        print(f"한글 폰트 설정 실패: {e}")
        return False

    return False

# 앱 시작 시 폰트 설정
setup_korean_font()

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

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
from text_parser import parse_lottery_text


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

        # 로그 버퍼 (파일 저장용)
        self.log_buffer = []
        self.log_file_path = os.path.join(os.path.expanduser("~"), ".lotto_qr_logs", f"log_{datetime.now().strftime('%Y%m%d')}.txt")
        os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)

        self.setup_ui()
        self.setup_drag_drop()
        self.setup_keyboard_shortcuts()

        # 윈도우 종료 이벤트 핸들러
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 초기 로그 메시지
        self.log("로또 QR 인식 앱 시작")
        self.log(f"웹 앱 URL: {WEB_APP_URL}")
        self.log(f"📁 로그 파일: {self.log_file_path}")

    def setup_ui(self):
        """UI 구성"""
        # 메인 프레임
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 상단: 파일 선택 영역
        file_frame = ttk.LabelFrame(main_frame, text="이미지 파일 선택", padding="10")
        file_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        self.file_path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.file_path_var, width=40, state="readonly").grid(row=0, column=0, padx=(0, 5))
        ttk.Button(file_frame, text="파일 선택", command=self.select_file).grid(row=0, column=1, padx=(0, 5))
        ttk.Button(file_frame, text="폴더 일괄처리", command=self.select_folder).grid(row=0, column=2, padx=(0, 5))
        ttk.Button(file_frame, text="📝 텍스트 입력", command=self.open_text_input_dialog).grid(row=0, column=3)

        # 좌측: 이미지 미리보기
        image_frame = ttk.LabelFrame(main_frame, text="이미지 미리보기 (드래그 앤 드롭 가능)", padding="10")
        image_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))

        self.image_label = ttk.Label(image_frame, text="이미지를 선택하거나\n여기로 드래그하세요", anchor="center",
                                     relief="groove", padding=20)
        self.image_label.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 이미지 프레임 그리드 설정
        image_frame.columnconfigure(0, weight=1)
        image_frame.rowconfigure(0, weight=1)

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

        # 데이터베이스 탭 (로컬)
        self.setup_database_tab()

        # 서버 정보 탭
        self.setup_server_info_tab()

        # 통계 탭
        self.setup_statistics_tab()

        # 하단: 프로그레스 바
        progress_frame = ttk.Frame(main_frame)
        progress_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, mode='determinate')
        self.progress_bar.pack(side=tk.TOP, fill=tk.X, padx=(0, 0), pady=(0, 5))

        # 하단: 상태바
        self.status_var = tk.StringVar()
        self.status_var.set("대기 중...")
        status_bar = ttk.Label(progress_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.TOP, fill=tk.X)

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
        ttk.Button(button_frame, text="📤 내보내기", command=self.export_data).pack(side=tk.LEFT, padx=(0, 5))

        # 그리드 가중치 설정
        db_frame.columnconfigure(0, weight=1)
        db_frame.rowconfigure(1, weight=1)
        stats_frame.columnconfigure(0, weight=1)
        rounds_frame.columnconfigure(0, weight=1)
        rounds_frame.rowconfigure(0, weight=1)

        # 초기 데이터 로드
        self.refresh_database_tab()

    def setup_server_info_tab(self):
        """서버 정보 탭 설정"""
        server_frame = ttk.Frame(self.notebook)
        self.notebook.add(server_frame, text="🌐 서버 정보")

        # 상단: 서버 연결 정보
        connection_frame = ttk.LabelFrame(server_frame, text="서버 연결 정보", padding="10")
        connection_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)

        self.server_info_text = tk.Text(connection_frame, height=4, width=70, wrap=tk.WORD)
        self.server_info_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.server_info_text.config(state=tk.DISABLED)

        # 중단: 서버 데이터베이스 통계
        stats_frame = ttk.LabelFrame(server_frame, text="서버 데이터베이스 통계", padding="10")
        stats_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        self.server_stats_text = tk.Text(stats_frame, height=12, width=70, wrap=tk.WORD, font=('Courier', 11))
        self.server_stats_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.server_stats_text.config(state=tk.DISABLED)

        # 스크롤바
        stats_scrollbar = ttk.Scrollbar(stats_frame, orient=tk.VERTICAL, command=self.server_stats_text.yview)
        stats_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.server_stats_text.configure(yscrollcommand=stats_scrollbar.set)

        # 하단: 버튼들
        button_frame = ttk.Frame(server_frame)
        button_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)

        ttk.Button(button_frame, text="🔄 새로고침", command=self.refresh_server_info).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="🔌 연결 테스트", command=self.test_connection).pack(side=tk.LEFT, padx=(0, 5))

        # 그리드 가중치 설정
        server_frame.columnconfigure(0, weight=1)
        server_frame.rowconfigure(1, weight=1)
        connection_frame.columnconfigure(0, weight=1)
        stats_frame.columnconfigure(0, weight=1)
        stats_frame.rowconfigure(0, weight=1)

        # 초기 서버 정보 로드
        self.refresh_server_info()

    def setup_statistics_tab(self):
        """통계 탭 설정"""
        stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(stats_frame, text="📊 통계")

        # 상단: 날짜 필터
        filter_frame = ttk.LabelFrame(stats_frame, text="기간 설정", padding="10")
        filter_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)

        ttk.Label(filter_frame, text="시작일:").grid(row=0, column=0, padx=5)
        self.start_date_var = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        self.start_date_entry = ttk.Entry(filter_frame, textvariable=self.start_date_var, width=12)
        self.start_date_entry.grid(row=0, column=1, padx=5)

        ttk.Label(filter_frame, text="종료일:").grid(row=0, column=2, padx=5)
        self.end_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        self.end_date_entry = ttk.Entry(filter_frame, textvariable=self.end_date_var, width=12)
        self.end_date_entry.grid(row=0, column=3, padx=5)

        ttk.Button(filter_frame, text="🔍 조회", command=self.refresh_statistics).grid(row=0, column=4, padx=5)
        ttk.Button(filter_frame, text="전체", command=self.show_all_statistics).grid(row=0, column=5, padx=5)

        # 중단: 차트 영역 (Notebook으로 탭 구성)
        chart_notebook = ttk.Notebook(stats_frame)
        chart_notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        # 차트 프레임들 생성
        self.daily_chart_frame = ttk.Frame(chart_notebook)
        chart_notebook.add(self.daily_chart_frame, text="일별 스캔")

        self.round_chart_frame = ttk.Frame(chart_notebook)
        chart_notebook.add(self.round_chart_frame, text="회차 분포")

        self.upload_chart_frame = ttk.Frame(chart_notebook)
        chart_notebook.add(self.upload_chart_frame, text="업로드 현황")

        self.hour_chart_frame = ttk.Frame(chart_notebook)
        chart_notebook.add(self.hour_chart_frame, text="시간대 분포")

        # 그리드 가중치 설정
        stats_frame.columnconfigure(0, weight=1)
        stats_frame.rowconfigure(1, weight=1)

        # 초기 통계 로드
        self.refresh_statistics()

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
            # 진행률 20%: QR 인식 시작
            self.root.after(0, lambda: self.update_progress(20, "QR 코드 인식 중..."))

            result = self.qr_processor.extract_qr_data(self.current_image_path)
            self.qr_data = result.get("data")

            # 진행률 60%: QR 인식 완료
            self.root.after(0, lambda: self.update_progress(60, "QR 데이터 파싱 중..."))

            self.root.after(0, self._update_qr_result, result)

            # 진행률 100%: 완료
            self.root.after(0, lambda: self.update_progress(100, "QR 처리 완료"))
            self.root.after(500, lambda: self.update_progress(0, "대기 중..."))

        except Exception as e:
            self.root.after(0, lambda: self.update_progress(0, "오류 발생"))
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
                # 서버 데이터베이스 통계 조회
                stats_result = self.api_client.get_server_database_stats()

                if stats_result["success"]:
                    stats = stats_result["data"]
                    message = f"✅ 서버 연결 성공\n\n"
                    message += f"📡 서버: {WEB_APP_URL}\n\n"
                    message += f"📊 데이터베이스 현황:\n"
                    message += f"  • 최신 회차: {stats.get('latest_round', 'N/A')}회\n"
                    message += f"  • 전체 회차: {stats.get('total_draws', 'N/A')}개\n"
                    message += f"  • 등록 사용자: {stats.get('total_users', 'N/A')}명\n"
                    message += f"  • 총 구매 기록: {stats.get('total_purchases', 'N/A')}건\n"

                    self.log("서버 연결 성공")
                    self.log(f"최신 회차: {stats.get('latest_round')}회")
                else:
                    message = f"✅ 서버 연결 성공\n서버: {WEB_APP_URL}\n\n⚠️ 통계 조회 실패: {stats_result.get('error', 'Unknown')}"
                    self.log("서버 연결 성공 (통계 조회 실패)")
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

        # 로그 버퍼에 추가 (파일 저장용)
        self.log_buffer.append(log_message)

        # 버퍼가 일정 크기 이상이면 파일에 자동 저장
        if len(self.log_buffer) >= 50:
            self.save_log_to_file()

    def save_log_to_file(self):
        """로그를 파일로 저장"""
        try:
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.writelines(self.log_buffer)
            self.log_buffer = []  # 버퍼 초기화
        except Exception as e:
            print(f"로그 파일 저장 실패: {e}")

    def setup_log_context_menu(self):
        """로그 텍스트 위젯의 컨텍스트 메뉴 설정"""
        # 컨텍스트 메뉴 생성
        self.log_context_menu = tk.Menu(self.root, tearoff=0)
        self.log_context_menu.add_command(label="전체 선택 (Ctrl+A)", command=self.select_all_log)
        self.log_context_menu.add_command(label="복사 (Ctrl+C)", command=self.copy_log_selection)
        self.log_context_menu.add_separator()
        self.log_context_menu.add_command(label="모든 로그 복사", command=self.copy_all_log)
        self.log_context_menu.add_command(label="로그 파일로 저장", command=self.export_log_to_file)
        self.log_context_menu.add_separator()
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

    def export_log_to_file(self):
        """로그를 수동으로 파일에 저장"""
        try:
            # 파일 저장 대화상자
            file_path = filedialog.asksaveasfilename(
                title="로그 파일 저장",
                defaultextension=".txt",
                filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")],
                initialfile=f"lotto_qr_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                parent=self.root
            )

            if file_path:
                # 현재 로그 텍스트 가져오기
                log_content = self.log_text.get("1.0", tk.END)

                # 파일에 저장
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(log_content)

                messagebox.showinfo("저장 완료", f"로그가 저장되었습니다:\n{file_path}")
                self.log(f"📄 로그 파일 저장: {os.path.basename(file_path)}")

        except Exception as e:
            messagebox.showerror("저장 실패", f"로그 저장 중 오류가 발생했습니다:\n{e}")
            print(f"로그 저장 오류: {e}")

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

    def setup_drag_drop(self):
        """드래그 앤 드롭 설정 (macOS/Windows/Linux 호환)"""
        if not DND_AVAILABLE:
            self.log("⚠️ 드래그 앤 드롭 라이브러리 미설치 (pip install tkinterdnd2)")
            return

        try:
            # Tkinter DND 이벤트 바인딩
            self.image_label.drop_target_register(DND_FILES)
            self.image_label.dnd_bind('<<Drop>>', self.on_drop)

            # 드래그 오버 시 시각적 피드백
            self.image_label.dnd_bind('<<DragEnter>>', self.on_drag_enter)
            self.image_label.dnd_bind('<<DragLeave>>', self.on_drag_leave)

            self.log("✅ 드래그 앤 드롭 활성화")
        except Exception as e:
            self.log(f"⚠️ 드래그 앤 드롭 설정 실패: {e}")

    def on_drop(self, event):
        """파일 드롭 이벤트 처리"""
        try:
            # 드롭된 파일 경로 가져오기
            files = self.root.tk.splitlist(event.data)

            if files:
                file_path = files[0]

                # 중괄호 제거 (macOS에서 경로에 포함될 수 있음)
                if file_path.startswith('{') and file_path.endswith('}'):
                    file_path = file_path[1:-1]

                # 파일 형식 검증
                if not file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff')):
                    messagebox.showwarning("경고", "지원하는 이미지 형식이 아닙니다.\n(JPG, PNG, BMP, TIFF)")
                    return

                # 파일 선택 처리
                self.current_image_path = file_path
                self.file_path_var.set(file_path)

                # 폴더 기억
                self.last_directory = os.path.dirname(file_path)
                self.save_last_directory()

                # 이미지 표시
                self.display_image(file_path)
                self.log(f"드래그 앤 드롭: {os.path.basename(file_path)}")

                # 자동 QR 인식
                self.auto_process_qr()

                # 드래그 피드백 제거
                self.on_drag_leave(None)

        except Exception as e:
            self.log(f"드래그 앤 드롭 오류: {e}")
            messagebox.showerror("오류", f"파일 드롭 처리 중 오류 발생: {e}")

    def on_drag_enter(self, event):
        """드래그 진입 시 시각적 피드백"""
        self.image_label.configure(relief="solid", borderwidth=2)

    def on_drag_leave(self, event):
        """드래그 떠남 시 피드백 제거"""
        self.image_label.configure(relief="groove", borderwidth=1)

    def setup_keyboard_shortcuts(self):
        """키보드 단축키 설정"""
        # Ctrl+O: 파일 열기
        self.root.bind('<Control-o>', lambda e: self.select_file())
        self.root.bind('<Command-o>', lambda e: self.select_file())  # macOS

        # Ctrl+Shift+O: 폴더 열기 (일괄 처리)
        self.root.bind('<Control-Shift-O>', lambda e: self.select_folder())
        self.root.bind('<Command-Shift-O>', lambda e: self.select_folder())  # macOS

        # Ctrl+R: QR 재인식
        self.root.bind('<Control-r>', lambda e: self.process_qr())
        self.root.bind('<Command-r>', lambda e: self.process_qr())  # macOS

        # Ctrl+U: 업로드
        self.root.bind('<Control-u>', lambda e: self.upload_data())
        self.root.bind('<Command-u>', lambda e: self.upload_data())  # macOS

        # Ctrl+T: 연결 테스트
        self.root.bind('<Control-t>', lambda e: self.test_connection())
        self.root.bind('<Command-t>', lambda e: self.test_connection())  # macOS

        # Ctrl+S: 데이터 내보내기
        self.root.bind('<Control-s>', lambda e: self.export_data())
        self.root.bind('<Command-s>', lambda e: self.export_data())  # macOS

        # F5: 데이터베이스 새로고침
        self.root.bind('<F5>', lambda e: self.refresh_database_tab())

        # ESC: 현재 동작 취소 / 창 닫기 (다이얼로그가 있으면)
        self.root.bind('<Escape>', lambda e: self.root.focus_set())

        self.log("⌨️ 키보드 단축키 활성화")

    def update_progress(self, percent: float, status: str = None):
        """프로그레스 바 및 상태 업데이트"""
        self.progress_var.set(percent)
        if status:
            self.status_var.set(status)

    def upload_with_retry(self, game_data: Dict, max_retries: int = 3) -> Dict:
        """자동 재시도 로직이 포함된 업로드"""
        import time

        for attempt in range(max_retries):
            try:
                result = self.api_client.upload_purchase_data(game_data)
                if result["success"]:
                    return result
                elif result.get("error") == "중복 데이터":
                    # 중복은 재시도하지 않음
                    return result
            except Exception as e:
                if attempt == max_retries - 1:
                    # 마지막 시도 실패 시 DB에 저장
                    if self.current_scan_id:
                        error_msg = f"업로드 실패 ({attempt + 1}회 시도): {str(e)}"
                        self.db.save_failed_upload(self.current_scan_id, error_msg)
                    raise
                # 지수 백오프 대기
                wait_time = 2 ** attempt
                self.root.after(0, lambda a=attempt+1, w=wait_time:
                               self.log(f"⚠️ 업로드 실패 (시도 {a}/{max_retries}), {w}초 후 재시도..."))
                time.sleep(wait_time)

        return {"success": False, "error": "최대 재시도 횟수 초과"}

    def select_folder(self):
        """폴더 선택 및 일괄 처리"""
        folder_path = filedialog.askdirectory(
            title="이미지 폴더를 선택하세요",
            initialdir=self.last_directory,
            parent=self.root
        )

        if folder_path:
            # 폴더 경로 기억
            self.last_directory = folder_path
            self.save_last_directory()

            # 이미지 파일 찾기
            image_files = []
            for filename in os.listdir(folder_path):
                if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff')):
                    image_files.append(os.path.join(folder_path, filename))

            if not image_files:
                messagebox.showinfo("알림", "선택한 폴더에 이미지 파일이 없습니다.")
                return

            # 일괄 처리 확인
            response = messagebox.askyesno(
                "일괄 처리 확인",
                f"{len(image_files)}개의 이미지를 일괄 처리하시겠습니까?\n\n"
                f"폴더: {os.path.basename(folder_path)}\n"
                f"예상 소요 시간: 약 {len(image_files) * 2}초"
            )

            if response:
                self.file_path_var.set(f"{folder_path} ({len(image_files)}개 파일)")
                self.log(f"📁 폴더 선택: {folder_path}")
                self.log(f"🔍 발견된 이미지: {len(image_files)}개")

                # 백그라운드에서 일괄 처리 시작
                threading.Thread(target=self.batch_process_images, args=(image_files,), daemon=True).start()

    def batch_process_images(self, image_files: list):
        """이미지 일괄 처리 (멀티스레딩)"""
        total = len(image_files)
        success_count = 0
        failed_count = 0
        skipped_count = 0
        failed_files = []

        self.root.after(0, lambda: self.log("=" * 50))
        self.root.after(0, lambda: self.log(f"📦 일괄 처리 시작: {total}개 파일"))
        self.root.after(0, lambda: self.log("=" * 50))

        for i, image_path in enumerate(image_files, 1):
            try:
                filename = os.path.basename(image_path)

                # 진행률 업데이트
                progress = (i / total) * 100
                status = f"처리 중: {i}/{total} ({filename})"
                self.root.after(0, lambda p=progress, s=status: self.update_progress(p, s))
                self.root.after(0, lambda i=i, t=total, f=filename: self.log(f"[{i}/{t}] {f}"))

                # QR 인식
                result = self.qr_processor.extract_qr_data(image_path)

                if result["success"] and result.get("all_data"):
                    # 로또 번호 파싱
                    parsed_data = None
                    for qr_info in result["all_data"]:
                        if isinstance(qr_info, dict) and qr_info.get('format') == 'url':
                            url = qr_info.get('url') or qr_info.get('raw_data')
                            if url and 'dhlottery.co.kr' in url:
                                parsed_data = self._extract_numbers_from_url(url)
                                if parsed_data:
                                    break

                    if parsed_data:
                        # DB에 저장
                        scan_id = self.db.save_qr_scan(
                            qr_data=result["all_data"][0] if result["all_data"] else {},
                            parsed_lottery_data=parsed_data,
                            image_path=image_path
                        )

                        success_count += 1
                        round_num = parsed_data.get('round', '?')
                        game_count = len(parsed_data.get('games', []))
                        self.root.after(0, lambda r=round_num, g=game_count:
                                       self.log(f"  ✅ 성공: {r}회차, {g}게임"))
                    else:
                        skipped_count += 1
                        self.root.after(0, lambda: self.log(f"  ⚠️ 스킵: 로또 번호 파싱 실패"))
                else:
                    skipped_count += 1
                    error_msg = result.get("error", "QR 코드 없음")
                    self.root.after(0, lambda e=error_msg: self.log(f"  ⚠️ 스킵: {e}"))

            except Exception as e:
                failed_count += 1
                failed_files.append((filename, str(e)))
                self.root.after(0, lambda f=filename, e=str(e): self.log(f"  ❌ 실패: {f} - {e}"))

        # 완료 메시지
        self.root.after(0, lambda: self.log("=" * 50))
        self.root.after(0, lambda: self.log("📊 일괄 처리 완료"))
        self.root.after(0, lambda s=success_count: self.log(f"  ✅ 성공: {s}개"))
        self.root.after(0, lambda k=skipped_count: self.log(f"  ⚠️ 스킵: {k}개"))
        self.root.after(0, lambda f=failed_count: self.log(f"  ❌ 실패: {f}개"))
        self.root.after(0, lambda: self.log("=" * 50))

        # 프로그레스 바 초기화
        self.root.after(0, lambda: self.update_progress(0, "일괄 처리 완료"))

        # 데이터베이스 탭 새로고침
        self.root.after(0, self.refresh_database_tab)

        # 결과 다이얼로그
        summary = f"일괄 처리 완료\n\n"
        summary += f"총 {total}개 파일\n"
        summary += f"✅ 성공: {success_count}개\n"
        summary += f"⚠️ 스킵: {skipped_count}개\n"
        summary += f"❌ 실패: {failed_count}개"

        if failed_files:
            summary += f"\n\n실패한 파일:\n"
            for filename, error in failed_files[:5]:  # 최대 5개만 표시
                summary += f"- {filename}: {error}\n"
            if len(failed_files) > 5:
                summary += f"... 외 {len(failed_files) - 5}개"

        self.root.after(0, lambda s=summary: messagebox.showinfo("일괄 처리 결과", s))

    def export_data(self):
        """데이터 내보내기"""
        # 내보내기 옵션 다이얼로그
        export_window = tk.Toplevel(self.root)
        export_window.title("데이터 내보내기")
        export_window.geometry("400x250")
        export_window.resizable(False, False)

        # 메인 프레임
        main_frame = ttk.Frame(export_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 형식 선택
        ttk.Label(main_frame, text="내보내기 형식:", font=("", 11, "bold")).pack(anchor=tk.W, pady=(0, 10))

        format_var = tk.StringVar(value="csv")
        ttk.Radiobutton(main_frame, text="CSV (엑셀에서 열기 좋음)", variable=format_var, value="csv").pack(anchor=tk.W, pady=5)
        ttk.Radiobutton(main_frame, text="JSON (전체 메타데이터 포함)", variable=format_var, value="json").pack(anchor=tk.W, pady=5)

        # 범위 선택
        ttk.Label(main_frame, text="내보내기 범위:", font=("", 11, "bold")).pack(anchor=tk.W, pady=(15, 10))

        range_var = tk.StringVar(value="all")
        ttk.Radiobutton(main_frame, text="전체 데이터", variable=range_var, value="all").pack(anchor=tk.W, pady=5)

        # 선택한 회차만
        selected_frame = ttk.Frame(main_frame)
        selected_frame.pack(anchor=tk.W, pady=5, fill=tk.X)

        ttk.Radiobutton(selected_frame, text="선택한 회차만:", variable=range_var, value="selected").pack(side=tk.LEFT)

        selected_round_var = tk.StringVar()
        selection = self.rounds_tree.selection()
        if selection:
            item = self.rounds_tree.item(selection[0])
            selected_round_var.set(str(item['values'][0]))
        else:
            selected_round_var.set("(회차 선택 안됨)")

        ttk.Label(selected_frame, textvariable=selected_round_var).pack(side=tk.LEFT, padx=(5, 0))

        # 버튼
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(20, 0), fill=tk.X)

        def do_export():
            format_type = format_var.get()
            range_type = range_var.get()

            # 선택 검증
            if range_type == "selected" and not selection:
                messagebox.showwarning("경고", "먼저 회차를 선택해주세요.")
                return

            # 파일 저장 대화상자
            default_filename = f"lotto_qr_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            if format_type == "csv":
                file_path = filedialog.asksaveasfilename(
                    title="CSV 파일 저장",
                    defaultextension=".csv",
                    filetypes=[("CSV 파일", "*.csv"), ("모든 파일", "*.*")],
                    initialfile=f"{default_filename}.csv"
                )
            else:
                file_path = filedialog.asksaveasfilename(
                    title="JSON 파일 저장",
                    defaultextension=".json",
                    filetypes=[("JSON 파일", "*.json"), ("모든 파일", "*.*")],
                    initialfile=f"{default_filename}.json"
                )

            if not file_path:
                return

            # 내보내기 실행
            try:
                round_filter = None
                if range_type == "selected":
                    round_filter = int(selected_round_var.get())

                if format_type == "csv":
                    success = self.db.export_to_csv(file_path, round_filter)
                else:
                    success = self.db.export_to_json(file_path, round_filter)

                if success:
                    self.log(f"✅ 데이터 내보내기 완료: {file_path}")
                    messagebox.showinfo("성공", f"데이터를 성공적으로 내보냈습니다.\n\n{file_path}")
                    export_window.destroy()
                else:
                    messagebox.showerror("실패", "데이터 내보내기에 실패했습니다.")

            except Exception as e:
                self.log(f"❌ 내보내기 오류: {e}")
                messagebox.showerror("오류", f"내보내기 중 오류가 발생했습니다:\n{e}")

        ttk.Button(button_frame, text="내보내기", command=do_export).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="취소", command=export_window.destroy).pack(side=tk.RIGHT)

    def open_text_input_dialog(self):
        """텍스트 입력 다이얼로그 열기"""
        dialog = tk.Toplevel(self.root)
        dialog.title("로또 구매 번호 텍스트 입력")
        dialog.geometry("700x600")

        # 설명
        desc_frame = ttk.Frame(dialog, padding="10")
        desc_frame.pack(fill=tk.X)

        ttk.Label(desc_frame, text="로또 구매 용지의 텍스트를 복사하여 붙여넣으세요", font=('Arial', 11, 'bold')).pack(anchor=tk.W)
        ttk.Label(desc_frame, text="예시: 인터넷 로또 구매 내역, 복권 용지 스캔 결과 등", foreground="gray").pack(anchor=tk.W, pady=(2, 0))

        # 텍스트 입력 영역
        text_frame = ttk.LabelFrame(dialog, text="텍스트 입력", padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text_widget = scrolledtext.ScrolledText(text_frame, height=20, width=70, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True)

        # 예시 텍스트
        example_text = """인터넷 로또 6/45 구매번호
복권 로또 645제 1191회
발 행 일 : 2025/09/27 (토) 10:08:16
추 첨 일 : 2025/09/27

A 수동 (낙첨)379152635
B 수동 (낙첨)3711121526
C 자동 (낙첨)2517223641
D 자동 (낙첨)132224283338
E 수동 (낙첨)121517303135"""

        text_widget.insert("1.0", example_text)

        # 버튼 프레임
        button_frame = ttk.Frame(dialog, padding="10")
        button_frame.pack(fill=tk.X)

        def parse_and_upload():
            """텍스트 파싱 및 업로드"""
            text = text_widget.get("1.0", tk.END).strip()

            if not text:
                messagebox.showwarning("경고", "텍스트를 입력해주세요.")
                return

            # 텍스트 파싱
            result = parse_lottery_text(text)

            if not result["success"]:
                messagebox.showerror("파싱 실패", f"텍스트 파싱에 실패했습니다.\n\n{result.get('error', 'Unknown error')}")
                return

            data = result["data"]

            # 파싱 결과 표시
            summary = f"파싱 결과:\n\n"
            summary += f"회차: {data['round']}회\n"
            summary += f"구매일: {data.get('purchase_date', 'N/A')}\n"
            summary += f"추첨일: {data.get('draw_date', 'N/A')}\n"
            summary += f"게임 수: {len(data['games'])}게임\n\n"

            for game in data['games']:
                summary += f"{game['game_type']} {game['mode']}: {game['numbers']}\n"

            confirmed = messagebox.askyesnocancel(
                "파싱 완료",
                f"{summary}\n\n서버에 업로드하시겠습니까?\n\n"
                f"예: 서버에 업로드\n"
                f"아니오: 로컬 DB에만 저장\n"
                f"취소: 아무것도 하지 않음"
            )

            if confirmed is None:  # 취소
                return

            try:
                # 로컬 DB에 저장
                for game in data['games']:
                    qr_data = {
                        'round': data['round'],
                        'numbers': game['numbers'],
                        'format': 'text_input',
                        'game_type': game['game_type'],
                        'mode': game['mode']
                    }

                    scan_id = self.db.save_qr_scan(
                        round_number=data['round'],
                        game_numbers={1: game['numbers']},
                        qr_data=json.dumps(qr_data),
                        qr_format='text_input'
                    )

                self.log(f"✅ 텍스트에서 {len(data['games'])}개 게임 파싱 완료")

                # 서버 업로드
                if confirmed:  # 예
                    if not self.api_client.is_authenticated:
                        messagebox.showwarning("인증 필요", "먼저 로그인해주세요.")
                        return

                    # 각 게임을 개별로 업로드
                    success_count = 0
                    for game in data['games']:
                        upload_data = {
                            'round': data['round'],
                            'draw_number': data['round'],
                            'numbers': game['numbers'],
                            'purchase_date': data.get('purchase_date', datetime.now().strftime('%Y-%m-%d'))
                        }

                        upload_result = self.api_client.upload_purchase_data(upload_data)
                        if upload_result['success']:
                            success_count += 1
                        else:
                            self.log(f"⚠️ 게임 {game['game_type']} 업로드 실패: {upload_result.get('error')}")

                    if success_count > 0:
                        messagebox.showinfo("성공", f"{success_count}/{len(data['games'])}개 게임이 서버에 업로드되었습니다.")
                        self.log(f"✅ {success_count}개 게임 업로드 완료")
                    else:
                        messagebox.showerror("실패", "게임 업로드에 모두 실패했습니다.")
                else:
                    messagebox.showinfo("완료", "로컬 DB에 저장되었습니다.")

                dialog.destroy()
                self.refresh_database_tab()

            except Exception as e:
                messagebox.showerror("오류", f"처리 중 오류가 발생했습니다:\n{e}")
                self.log(f"❌ 텍스트 처리 오류: {e}")

        ttk.Button(button_frame, text="파싱 및 저장", command=parse_and_upload).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="취소", command=dialog.destroy).pack(side=tk.LEFT)

    # ======================
    # 통계 및 시각화 메서드
    # ======================

    def refresh_statistics(self):
        """통계 데이터 새로고침 및 차트 업데이트"""
        try:
            start_date = self.start_date_var.get() + " 00:00:00"
            end_date = self.end_date_var.get() + " 23:59:59"

            # 데이터베이스에서 통계 데이터 가져오기
            stats_data = self.db.get_statistics_for_visualization(start_date, end_date)

            # 각 차트 업데이트
            self.update_daily_scan_chart(stats_data['daily_scans'])
            self.update_round_distribution_chart(stats_data['round_distribution'])
            self.update_upload_stats_chart(stats_data['upload_stats'])
            self.update_hourly_distribution_chart(stats_data['hourly_distribution'])

            self.log(f"✅ 통계 업데이트 완료 ({start_date.split()[0]} ~ {end_date.split()[0]})")

        except Exception as e:
            self.log(f"⚠️ 통계 로드 실패: {e}")
            messagebox.showerror("오류", f"통계 데이터를 불러올 수 없습니다:\n{e}")

    def show_all_statistics(self):
        """전체 기간 통계 표시"""
        # 날짜 필터 초기화 (매우 먼 과거 ~ 현재)
        self.start_date_var.set("2020-01-01")
        self.end_date_var.set(datetime.now().strftime('%Y-%m-%d'))
        self.refresh_statistics()

    def update_daily_scan_chart(self, daily_scans: List[Dict]):
        """일별 스캔 횟수 차트 업데이트"""
        # 기존 차트 제거
        for widget in self.daily_chart_frame.winfo_children():
            widget.destroy()

        if not daily_scans:
            ttk.Label(self.daily_chart_frame, text="데이터가 없습니다", font=('Arial', 12)).pack(pady=20)
            return

        # 차트 생성
        fig = Figure(figsize=(8, 5), dpi=100)
        ax = fig.add_subplot(111)

        dates = [item['date'] for item in daily_scans]
        counts = [item['count'] for item in daily_scans]

        ax.plot(dates, counts, marker='o', linestyle='-', color='#4CAF50', linewidth=2)
        ax.set_xlabel('날짜', fontsize=10)
        ax.set_ylabel('스캔 횟수', fontsize=10)
        ax.set_title('일별 QR 스캔 횟수', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)

        # x축 레이블 회전
        fig.autofmt_xdate()

        # Tkinter 캔버스에 차트 추가
        canvas = FigureCanvasTkAgg(fig, master=self.daily_chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def update_round_distribution_chart(self, round_distribution: List[Dict]):
        """회차별 스캔 분포 차트 업데이트"""
        # 기존 차트 제거
        for widget in self.round_chart_frame.winfo_children():
            widget.destroy()

        if not round_distribution:
            ttk.Label(self.round_chart_frame, text="데이터가 없습니다", font=('Arial', 12)).pack(pady=20)
            return

        # 차트 생성
        fig = Figure(figsize=(8, 5), dpi=100)
        ax = fig.add_subplot(111)

        rounds = [str(item['round']) for item in round_distribution]
        counts = [item['count'] for item in round_distribution]

        ax.bar(rounds, counts, color='#2196F3', alpha=0.7)
        ax.set_xlabel('회차', fontsize=10)
        ax.set_ylabel('스캔 횟수', fontsize=10)
        ax.set_title('회차별 스캔 분포 (최근 20개)', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')

        # x축 레이블 회전
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

        # Tkinter 캔버스에 차트 추가
        canvas = FigureCanvasTkAgg(fig, master=self.round_chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def update_upload_stats_chart(self, upload_stats: Dict):
        """업로드 성공률 차트 업데이트"""
        # 기존 차트 제거
        for widget in self.upload_chart_frame.winfo_children():
            widget.destroy()

        success = upload_stats['success']
        failed = upload_stats['failed']
        pending = upload_stats['pending']

        if success == 0 and failed == 0 and pending == 0:
            ttk.Label(self.upload_chart_frame, text="데이터가 없습니다", font=('Arial', 12)).pack(pady=20)
            return

        # 차트 생성
        fig = Figure(figsize=(8, 5), dpi=100)
        ax = fig.add_subplot(111)

        labels = []
        sizes = []
        colors = []

        if success > 0:
            labels.append(f'성공 ({success})')
            sizes.append(success)
            colors.append('#4CAF50')

        if failed > 0:
            labels.append(f'실패 ({failed})')
            sizes.append(failed)
            colors.append('#F44336')

        if pending > 0:
            labels.append(f'대기 ({pending})')
            sizes.append(pending)
            colors.append('#FFC107')

        ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        ax.set_title('업로드 현황', fontsize=12, fontweight='bold')

        # Tkinter 캔버스에 차트 추가
        canvas = FigureCanvasTkAgg(fig, master=self.upload_chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def update_hourly_distribution_chart(self, hourly_distribution: List[Dict]):
        """시간대별 스캔 분포 차트 업데이트"""
        # 기존 차트 제거
        for widget in self.hour_chart_frame.winfo_children():
            widget.destroy()

        if not hourly_distribution:
            ttk.Label(self.hour_chart_frame, text="데이터가 없습니다", font=('Arial', 12)).pack(pady=20)
            return

        # 0-23시 전체 시간대 생성 (데이터 없는 시간은 0)
        hours = list(range(24))
        counts = [0] * 24

        for item in hourly_distribution:
            hour = item['hour']
            count = item['count']
            if 0 <= hour < 24:
                counts[hour] = count

        # 차트 생성
        fig = Figure(figsize=(8, 5), dpi=100)
        ax = fig.add_subplot(111)

        ax.bar(hours, counts, color='#9C27B0', alpha=0.7)
        ax.set_xlabel('시간 (시)', fontsize=10)
        ax.set_ylabel('스캔 횟수', fontsize=10)
        ax.set_title('시간대별 스캔 분포', fontsize=12, fontweight='bold')
        ax.set_xticks(range(0, 24, 2))
        ax.grid(True, alpha=0.3, axis='y')

        # Tkinter 캔버스에 차트 추가
        canvas = FigureCanvasTkAgg(fig, master=self.hour_chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def refresh_server_info(self):
        """서버 정보 새로고침"""
        try:
            # 서버 연결 정보 업데이트
            server_info = self.api_client.get_server_info()

            self.server_info_text.config(state=tk.NORMAL)
            self.server_info_text.delete("1.0", tk.END)

            info_text = f"서버 이름: {server_info['server_name']}\n"
            info_text += f"서버 URL: {server_info['server_url']}\n"
            info_text += f"설명: {server_info['description']}\n"
            info_text += f"인증 상태: {'✅ 로그인됨' if server_info['is_authenticated'] else '❌ 로그인 필요'}"

            self.server_info_text.insert("1.0", info_text)
            self.server_info_text.config(state=tk.DISABLED)

            # 서버 데이터베이스 통계 조회
            self.server_stats_text.config(state=tk.NORMAL)
            self.server_stats_text.delete("1.0", tk.END)

            self.server_stats_text.insert("1.0", "서버 데이터베이스 통계를 조회 중...\n")
            self.server_stats_text.config(state=tk.DISABLED)

            # 백그라운드 스레드로 통계 조회
            threading.Thread(target=self._fetch_server_stats_thread, daemon=True).start()

        except Exception as e:
            self.log(f"⚠️ 서버 정보 로드 실패: {e}")

    def _fetch_server_stats_thread(self):
        """서버 통계 조회 스레드"""
        try:
            stats_result = self.api_client.get_server_database_stats()

            if stats_result["success"]:
                stats = stats_result["data"]

                stats_text = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                stats_text += "📊 서버 데이터베이스 현황\n"
                stats_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

                stats_text += f"🎯 로또 데이터:\n"
                stats_text += f"  • 최신 회차: {stats.get('latest_round', 'N/A')}회\n"
                stats_text += f"  • 전체 회차: {stats.get('total_draws', 'N/A')}개\n"
                stats_text += f"  • 데이터 범위: {stats.get('earliest_round', 'N/A')}회 ~ {stats.get('latest_round', 'N/A')}회\n\n"

                stats_text += f"👥 사용자 정보:\n"
                stats_text += f"  • 등록 사용자: {stats.get('total_users', 'N/A')}명\n"
                stats_text += f"  • 활성 사용자: {stats.get('active_users', 'N/A')}명\n\n"

                stats_text += f"🎫 구매 기록:\n"
                stats_text += f"  • 총 구매 건수: {stats.get('total_purchases', 'N/A')}건\n"
                stats_text += f"  • 총 게임 수: {stats.get('total_games', 'N/A')}게임\n\n"

                if stats.get('winning_stats'):
                    winning = stats['winning_stats']
                    stats_text += f"🏆 당첨 통계:\n"
                    stats_text += f"  • 1등 당첨: {winning.get('rank_1', 0)}건\n"
                    stats_text += f"  • 2등 당첨: {winning.get('rank_2', 0)}건\n"
                    stats_text += f"  • 3등 당첨: {winning.get('rank_3', 0)}건\n"
                    stats_text += f"  • 4등 당첨: {winning.get('rank_4', 0)}건\n"
                    stats_text += f"  • 5등 당첨: {winning.get('rank_5', 0)}건\n\n"

                stats_text += f"📅 마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                stats_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

                self.root.after(0, lambda: self._update_server_stats_display(stats_text))
                self.root.after(0, lambda: self.log("✅ 서버 통계 조회 완료"))
            else:
                error_text = f"⚠️ 서버 통계 조회 실패\n\n오류: {stats_result.get('error', 'Unknown')}"
                self.root.after(0, lambda: self._update_server_stats_display(error_text))
                self.root.after(0, lambda: self.log(f"⚠️ 서버 통계 조회 실패: {stats_result.get('error')}"))

        except Exception as e:
            error_text = f"⚠️ 서버 통계 조회 중 오류 발생\n\n상세: {str(e)}"
            self.root.after(0, lambda: self._update_server_stats_display(error_text))
            self.root.after(0, lambda: self.log(f"⚠️ 서버 통계 조회 오류: {e}"))

    def _update_server_stats_display(self, text: str):
        """서버 통계 텍스트 업데이트"""
        self.server_stats_text.config(state=tk.NORMAL)
        self.server_stats_text.delete("1.0", tk.END)
        self.server_stats_text.insert("1.0", text)
        self.server_stats_text.config(state=tk.DISABLED)

    def on_closing(self):
        """앱 종료 시 로그 저장 및 정리"""
        try:
            # 버퍼에 남은 로그 저장
            if self.log_buffer:
                self.save_log_to_file()
                print(f"✅ 로그 저장 완료: {self.log_file_path}")
        except Exception as e:
            print(f"⚠️ 종료 시 로그 저장 실패: {e}")
        finally:
            # 윈도우 종료
            self.root.destroy()


def main():
    """메인 함수"""
    # DND 지원이 있으면 TkinterDnD root 사용
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    app = LottoQRApp(root)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
