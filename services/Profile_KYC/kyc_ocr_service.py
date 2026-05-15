import re
import os
import cv2
import fitz
import numpy as np
import pytesseract

from rapidfuzz import fuzz


# ============================================================================
# TESSERACT CONFIG
# ============================================================================

TESSERACT_PATH = os.getenv(
    "TESSERACT_PATH",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


class KYCService:

    # =========================================================================
    # PDF DIRECT TEXT EXTRACTION
    # =========================================================================
    @staticmethod
    def _extract_text_from_pdf_direct(path: str) -> str:

        try:

            doc = fitz.open(path)

            if len(doc) > 20:
                raise Exception("PDF exceeds maximum 20 pages")

            text = ""

            for i, page in enumerate(doc):

                if i >= 2:
                    break

                text += page.get_text()

            doc.close()

            return text.strip()

        except Exception:
            return ""

    # =========================================================================
    # PDF TO IMAGES
    # =========================================================================
    @staticmethod
    def _pdf_to_images(path: str) -> list:

        doc = fitz.open(path)

        if len(doc) > 20:
            raise Exception("PDF exceeds maximum 20 pages")

        images = []

        for i, page in enumerate(doc):

            if i >= 2:
                break

            mat = fitz.Matrix(2, 2)

            pix = page.get_pixmap(
                matrix=mat,
                colorspace=fitz.csGRAY
            )

            arr = np.frombuffer(
                pix.samples,
                dtype=np.uint8
            ).reshape(pix.height, pix.width)

            images.append(arr)

        doc.close()

        return images

    # =========================================================================
    # GENERAL PREPROCESS
    # =========================================================================
    @staticmethod
    def _preprocess_gray(gray: np.ndarray) -> np.ndarray:

        h, w = gray.shape[:2]

        if w < 1200:

            scale = 1200 / w

            gray = cv2.resize(
                gray,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_LANCZOS4
            )

        gray = cv2.fastNlMeansDenoising(gray, h=8)

        thresh = cv2.threshold(
            gray,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )[1]

        return thresh

    # =========================================================================
    # AADHAAR PREPROCESS
    # =========================================================================
    @staticmethod
    def _preprocess_aadhaar(gray: np.ndarray) -> np.ndarray:

        h, w = gray.shape[:2]

        if w < 1600:

            scale = 1600 / w

            gray = cv2.resize(
                gray,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_LANCZOS4
            )

        gray = cv2.fastNlMeansDenoising(gray, h=5)

        kernel = np.array([
            [-1, -1, -1],
            [-1,  9, -1],
            [-1, -1, -1]
        ])

        gray = cv2.filter2D(gray, -1, kernel)

        gray = cv2.convertScaleAbs(
            gray,
            alpha=1.5,
            beta=10
        )

        thresh = cv2.threshold(
            gray,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )[1]

        return thresh

    # =========================================================================
    # EXTRACT TEXT
    # =========================================================================
    @staticmethod
    def extract_text(path: str, lang: str = "eng") -> str:

        if not os.path.exists(path):
            raise Exception(f"File not found: {path}")

        ext = os.path.splitext(path)[1].lower()

        if ext not in [".pdf", ".jpg", ".jpeg", ".png"]:
            raise Exception(f"Unsupported file type: {ext}")

        # =========================================================================
        # PDF
        # =========================================================================

        if ext == ".pdf":

            direct_text = KYCService._extract_text_from_pdf_direct(path)

            if direct_text and len(direct_text) > 50:

                print("========== OCR TEXT ==========")
                print(direct_text[:3000])
                print("================================")

                return direct_text

            pages = KYCService._pdf_to_images(path)

            all_text = []

            for gray in pages:

                thresh = KYCService._preprocess_gray(gray)

                text = pytesseract.image_to_string(
                    thresh,
                    config=(
                        "--oem 3 --psm 11 "
                        "-c preserve_interword_spaces=1"
                    )
                )

                all_text.append(text)

            final_text = "\n".join(all_text)

            print("========== OCR TEXT ==========")
            print(final_text[:3000])
            print("================================")

            return final_text

        # =========================================================================
        # IMAGE
        # =========================================================================

        img = cv2.imread(path)

        if img is None:
            raise Exception(f"Unable to read image: {path}")

        filename = os.path.basename(path).upper()

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        if "AADHAAR" in filename:
            thresh = KYCService._preprocess_aadhaar(gray)
        else:
            thresh = KYCService._preprocess_gray(gray)

        text = pytesseract.image_to_string(
            thresh,
            lang=lang,
            config=(
                "--oem 3 --psm 11 "
                "-c preserve_interword_spaces=1 "
            )
        )

        # =========================================================================
        # EXTRA DIGIT OCR FOR AADHAAR
        # =========================================================================

        if "AADHAAR" in filename:

            digit_text = pytesseract.image_to_string(
                thresh,
                config=(
                    "--oem 3 --psm 11 "
                    "-c tessedit_char_whitelist=0123456789 "
                )
            )

            text += "\n" + digit_text

        print("========== OCR TEXT ==========")
        print(text[:3000])
        print("================================")

        return text

    # =========================================================================
    # NORMALIZE NAME
    # =========================================================================
    @staticmethod
    def normalize_name(name: str) -> str:

        if not name:
            return ""

        name = name.upper()

        name = re.sub(r'[^A-Z\s]', '', name)

        return re.sub(r'\s+', ' ', name).strip()

    # =========================================================================
    # NAME MATCH
    # =========================================================================
    @staticmethod
    def name_match(n1: str, n2: str):

        n1 = KYCService.normalize_name(n1)
        n2 = KYCService.normalize_name(n2)

        if not n1 or not n2:
            return False, 0

        score = fuzz.token_sort_ratio(n1, n2)

        return score >= 80, score

    # =========================================================================
    # NORMALIZE DOB
    # =========================================================================
    @staticmethod
    def _normalize_dob(dob_value) -> str | None:

        if dob_value is None:
            return None

        if hasattr(dob_value, 'day'):

            return (
                f"{dob_value.day:02d}/"
                f"{dob_value.month:02d}/"
                f"{dob_value.year}"
            )

        s = str(dob_value).strip()

        m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', s)

        if m:
            return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"

        m = re.fullmatch(
            r'(\d{2})[/\-\.](\d{2})[/\-\.](\d{4})',
            s
        )

        if m:
            return f"{m.group(1)}/{m.group(2)}/{m.group(3)}"

        return None