"""
Image preprocessing for lottery ticket OCR
"""

import cv2
import numpy as np
from PIL import Image
from config import MAX_IMAGE_SIZE


class ImagePreprocessor:
    def __init__(self):
        pass

    def preprocess_for_ocr(self, image_path: str) -> np.ndarray:
        """
        이미지를 OCR에 최적화된 형태로 전처리
        """
        # PIL로 이미지 로드 (EXIF 처리용)
        from PIL import Image
        pil_image = Image.open(image_path)

        # EXIF 방향 정보 처리
        pil_image = self._fix_orientation(pil_image)

        # PIL에서 OpenCV로 변환
        import numpy as np
        image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

        # 크기 조정
        image = self._resize_image(image)

        # 그레이스케일 변환
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 노이즈 제거 강화
        denoised = cv2.medianBlur(gray, 5)
        denoised = cv2.bilateralFilter(denoised, 9, 75, 75)

        # 대비 향상
        enhanced = self._enhance_contrast(denoised)

        # 샤프닝 필터 적용
        sharpened = self._sharpen_image(enhanced)

        # 이진화
        binary = self._binarize(sharpened)

        return binary

    def _resize_image(self, image: np.ndarray) -> np.ndarray:
        """이미지 크기 조정"""
        height, width = image.shape[:2]
        max_width, max_height = MAX_IMAGE_SIZE

        if width > max_width or height > max_height:
            # 비율 유지하며 크기 조정
            ratio = min(max_width / width, max_height / height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)

        return image

    def _enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """대비 향상"""
        # CLAHE (Contrast Limited Adaptive Histogram Equalization) 적용
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        return clahe.apply(image)

    def _sharpen_image(self, image: np.ndarray) -> np.ndarray:
        """이미지 샤프닝으로 선명도 향상"""
        # 언샤프 마스킹 커널
        kernel = np.array([[-1,-1,-1],
                          [-1, 9,-1],
                          [-1,-1,-1]])
        sharpened = cv2.filter2D(image, -1, kernel)

        # 원본과 샤프닝된 이미지를 적절히 조합
        return cv2.addWeighted(image, 0.5, sharpened, 0.5, 0)

    def _binarize(self, image: np.ndarray) -> np.ndarray:
        """적응적 이진화"""
        # Otsu's thresholding
        _, binary = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 모폴로지 연산으로 노이즈 제거
        kernel = np.ones((2, 2), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        return binary

    def detect_number_regions(self, image: np.ndarray) -> list:
        """
        번호가 있을 것으로 예상되는 영역 감지
        """
        # 윤곽선 검출
        contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        regions = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)

            # 번호 크기에 적합한 영역만 선택
            if 15 < w < 100 and 15 < h < 100:
                # 가로세로 비율 체크 (숫자는 대략 1:1.5 비율)
                ratio = h / w
                if 0.5 < ratio < 3.0:
                    regions.append((x, y, w, h))

        # x 좌표 기준으로 정렬 (왼쪽부터)
        regions.sort(key=lambda r: r[0])

        return regions

    def extract_region(self, image: np.ndarray, region: tuple) -> np.ndarray:
        """특정 영역 추출"""
        x, y, w, h = region
        return image[y:y+h, x:x+w]

    def rotate_image(self, image: np.ndarray, angle: float) -> np.ndarray:
        """이미지 회전"""
        height, width = image.shape[:2]
        center = (width // 2, height // 2)

        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(image, rotation_matrix, (width, height),
                                flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

        return rotated

    def detect_skew(self, image: np.ndarray) -> float:
        """이미지 기울기 감지"""
        try:
            # Hough 변환으로 직선 검출
            edges = cv2.Canny(image, 50, 150, apertureSize=3)
            lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)

            if lines is not None and len(lines) > 0:
                angles = []
                for line in lines[:10]:  # 상위 10개 직선만 사용
                    try:
                        rho, theta = line[0]  # line[0]에서 rho, theta 추출
                        angle = theta * 180 / np.pi
                        if angle < 45:
                            angles.append(angle)
                        elif angle > 135:
                            angles.append(angle - 180)
                    except (IndexError, ValueError):
                        continue

                if angles:
                    return np.median(angles)

        except Exception as e:
            print(f"기울기 감지 오류: {e}")

        return 0.0

    def _fix_orientation(self, image):
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
