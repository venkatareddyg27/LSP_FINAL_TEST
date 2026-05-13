import re
import os
import cv2
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

    pytesseract.pytesseract.tesseract_cmd = (
        TESSERACT_PATH
    )


class KYCService:

    # =========================================================================
    # PDF DIRECT TEXT EXTRACTION
    # =========================================================================
    @staticmethod
    def _extract_text_from_pdf_direct(
        path: str
    ) -> str:

        try:

            import fitz

            doc = fitz.open(path)

            if len(doc) > 20:

                raise Exception(
                    "PDF exceeds maximum "
                    "20 pages"
                )

            text = ""

            # =========================================================
            # LIMIT TO FIRST 2 PAGES
            # =========================================================
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
    def _pdf_to_images(
        path: str
    ) -> list:

        try:

            import fitz

        except ImportError:

            raise Exception(
                "PyMuPDF not installed. "
                "Run: pip install pymupdf"
            )

        doc = fitz.open(path)

        if len(doc) > 20:

            raise Exception(
                "PDF exceeds maximum "
                "20 pages"
            )

        images = []

        # =========================================================
        # LIMIT TO FIRST 2 PAGES
        # =========================================================
        for i, page in enumerate(doc):

            if i >= 2:
                break

            # =====================================================
            # LOWER DPI FOR FASTER OCR
            # =====================================================
            mat = fitz.Matrix(
                1.5,
                1.5
            )

            pix = page.get_pixmap(
                matrix=mat,
                colorspace=fitz.csGRAY
            )

            arr = np.frombuffer(
                pix.samples,
                dtype=np.uint8
            ).reshape(
                pix.height,
                pix.width
            )

            images.append(arr)

        doc.close()

        return images

    # =========================================================================
    # IMAGE PREPROCESS
    # =========================================================================
    @staticmethod
    def _preprocess_gray(
        gray: np.ndarray
    ) -> np.ndarray:

        h, w = gray.shape[:2]

        # =========================================================
        # REDUCED UPSCALE SIZE
        # =========================================================
        if w < 900:

            scale = 900 / w

            gray = cv2.resize(
                gray,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_CUBIC
            )

        gray = cv2.fastNlMeansDenoising(
            gray,
            h=10
        )

        thresh = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            10,
        )

        if (
            thresh is None
            or thresh.size == 0
        ):

            raise Exception(
                "Invalid image after preprocessing"
            )

        return thresh

    # =========================================================================
    # TEXT EXTRACTION
    # =========================================================================
    @staticmethod
    def extract_text(
        path: str,
        lang: str = "eng"
    ) -> str:

        if not os.path.exists(path):

            raise Exception(
                f"File not found: {path}"
            )

        ext = os.path.splitext(
            path
        )[1].lower()

        allowed = [
            ".pdf",
            ".jpg",
            ".jpeg",
            ".png"
        ]

        if ext not in allowed:

            raise Exception(
                f"Unsupported file type: {ext}"
            )

        # =====================================================================
        # PDF
        # =====================================================================
        if ext == ".pdf":

            direct_text = (
                KYCService
                ._extract_text_from_pdf_direct(
                    path
                )
            )

            # =====================================================
            # RETURN DIRECT TEXT IF AVAILABLE
            # =====================================================
            if (
                direct_text
                and len(direct_text) > 50
            ):

                print(
                    "========== OCR TEXT =========="
                )

                print(
                    direct_text[:3000]
                )

                print(
                    "================================"
                )

                return direct_text

            pages = (
                KYCService
                ._pdf_to_images(path)
            )

            all_text = []

            for gray in pages:

                thresh = (
                    KYCService
                    ._preprocess_gray(gray)
                )

                text = (
                    pytesseract
                    .image_to_string(
                        thresh,
                        lang=lang,
                        config=(
                            "--oem 3 "
                            "--psm 6 "
                            "-c preserve_interword_spaces=1"
                        ),
                        timeout=20
                    )
                )

                all_text.append(text)

            final_text = "\n".join(all_text)

            print(
                "========== OCR TEXT =========="
            )

            print(
                final_text[:3000]
            )

            print(
                "================================"
            )

            return final_text

        # =====================================================================
        # IMAGE FILES
        # =====================================================================

        img = cv2.imread(path)

        if img is None:

            raise Exception(
                f"Image not readable: {path}"
            )

        h, w = img.shape[:2]

        # =========================================================
        # REDUCED UPSCALE SIZE
        # =========================================================
        if w < 900:

            scale = 900 / w

            img = cv2.resize(
                img,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_CUBIC
            )

        gray = cv2.cvtColor(
            img,
            cv2.COLOR_BGR2GRAY
        )

        gray = cv2.fastNlMeansDenoising(
            gray,
            h=10
        )

        thresh = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            10,
        )

        if (
            thresh is None
            or thresh.size == 0
        ):

            raise Exception(
                "Invalid image after preprocessing"
            )

        text = pytesseract.image_to_string(
            thresh,
            lang=lang,
            config=(
                "--oem 3 "
                "--psm 6 "
                "-c preserve_interword_spaces=1"
            ),
            timeout=20
        )

        print(
            "========== OCR TEXT =========="
        )

        print(
            text[:3000]
        )

        print(
            "================================"
        )

        return text

    # =========================================================================
    # NORMALIZE NAME
    # =========================================================================
    @staticmethod
    def normalize_name(
        name: str
    ) -> str:

        if not name:
            return ""

        name = name.upper()

        name = re.sub(
            r'[^A-Z\s]',
            '',
            name
        )

        return re.sub(
            r'\s+',
            ' ',
            name
        ).strip()

    # =========================================================================
    # NAME MATCH
    # =========================================================================
    @staticmethod
    def name_match(
        n1: str,
        n2: str
    ):

        n1 = KYCService.normalize_name(n1)

        n2 = KYCService.normalize_name(n2)

        if not n1 or not n2:

            return False, 0

        score = fuzz.token_sort_ratio(
            n1,
            n2
        )

        return score >= 80, score

    # =========================================================================
    # NORMALIZE DOB
    # =========================================================================
    @staticmethod
    def _normalize_dob(
        dob_value
    ) -> str | None:

        if dob_value is None:

            return None

        if hasattr(
            dob_value,
            'day'
        ):

            return (
                f"{dob_value.day:02d}/"
                f"{dob_value.month:02d}/"
                f"{dob_value.year}"
            )

        s = str(dob_value).strip()

        m = re.fullmatch(
            r'(\d{4})-(\d{2})-(\d{2})',
            s
        )

        if m:

            return (
                f"{m.group(3)}/"
                f"{m.group(2)}/"
                f"{m.group(1)}"
            )

        m = re.fullmatch(
            r'(\d{2})[/\-\.](\d{2})[/\-\.](\d{4})',
            s
        )

        if m:

            return (
                f"{m.group(1)}/"
                f"{m.group(2)}/"
                f"{m.group(3)}"
            )

        return None

    # =========================================================================
    # PAN PROCESSING
    # =========================================================================
    @staticmethod
    def process_pan(
        text: str,
        user
    ) -> dict:

        lines = [
            l.strip()
            for l in text.splitlines()
            if l.strip()
        ]

        pan = None

        for line in lines:

            m = re.search(
                r'\b([A-Z]{5}[0-9]{4}[A-Z])\b',
                line
            )

            if m:

                pan = m.group(1)
                break

        excluded_words = [

            "INCOME TAX",
            "DEPARTMENT",
            "GOVT",
            "GOVERNMENT",
            "INDIA",
            "FATHER",
            "SIGNATURE",
            "PERMANENT",
            "ACCOUNT",
            "CARD",
            "DATE",
            "BIRTH"
        ]

        candidate_names = []

        for line in lines:

            upper = line.upper()

            if re.search(
                r'[A-Z]{5}[0-9]{4}[A-Z]',
                upper
            ):
                continue

            if re.search(r'\d', upper):
                continue

            if any(
                word in upper
                for word in excluded_words
            ):
                continue

            cleaned = re.sub(
                r'[^A-Za-z\s]',
                '',
                line
            ).strip()

            cleaned = re.sub(
                r'\s+',
                ' ',
                cleaned
            )

            if len(cleaned) >= 5:

                candidate_names.append(
                    cleaned
                )

        extracted_name = ""

        best_score = 0

        for candidate in candidate_names:

            matched, score = (
                KYCService.name_match(
                    user.full_name,
                    candidate
                )
            )

            if score > best_score:

                best_score = score

                extracted_name = candidate

        matched = best_score >= 80

        pan_match = (
            pan == user.pan_number
            if pan and user.pan_number
            else False
        )

        failed_reasons = []

        if not pan_match:

            failed_reasons.append(
                f"PAN number mismatch: "
                f"extracted '{pan}', "
                f"expected "
                f"'{user.pan_number}'"
            )

        if not matched:

            failed_reasons.append(
                f"Name mismatch: "
                f"extracted "
                f"'{extracted_name}', "
                f"expected "
                f"'{user.full_name}' "
                f"(score: {round(best_score,1)})"
            )

        masked_pan = None

        if pan:

            masked_pan = (
                f"{pan[:5]}XXXX{pan[-1]}"
            )

        return {

            "extracted": {

                "pan_number": masked_pan,

                "name": extracted_name,
            },

            "comparison": {

                "pan_match": pan_match,

                "name_match": matched,

                "name_score": round(
                    best_score,
                    2
                ),

                "verified": (
                    pan_match and matched
                ),
            },

            "user_data": {

                "pan_number": (
                    user.pan_number
                ),

                "full_name": (
                    user.full_name
                ),
            },

            "failed_reasons": (
                failed_reasons
            ),
        }

    # =========================================================================
    # AADHAAR PROCESSING
    # =========================================================================
    @staticmethod
    def process_aadhaar(
        text: str,
        user
    ) -> dict:

        lines = [
            l.strip()
            for l in text.splitlines()
            if l.strip()
        ]

        # =====================================================
        # AADHAAR NUMBER
        # =====================================================
        aadhaar = None

        for line in lines:

            m = re.search(
                r'\b(\d{4}[\s\-]?\d{4}[\s\-]?\d{4})\b',
                line
            )

            if m:

                candidate = re.sub(
                    r'[\s\-]',
                    '',
                    m.group()
                )

                if len(candidate) == 12:

                    aadhaar = candidate
                    break

        # =====================================================
        # DOB EXTRACTION
        # =====================================================
        dob = None

        for line in lines:

            clean_line = line.upper()

            # ================================================
            # FULL DOB
            # ================================================
            m = re.search(

                r'(\d{2})[/\-\.](\d{2})[/\-\.](\d{4})',

                clean_line
            )

            if m:

                dob = (
                    f"{m.group(1)}/"
                    f"{m.group(2)}/"
                    f"{m.group(3)}"
                )

                break

            # ================================================
            # YEAR OF BIRTH ONLY
            # ================================================
            yob = re.search(

                r'(19\d{2}|20\d{2})',

                clean_line
            )

            if yob:

                dob = yob.group(1)

        # =====================================================
        # NORMALIZE USER DOB
        # =====================================================
        user_dob = (
            KYCService._normalize_dob(
                user.dob
            )
        )

        if dob:

            dob = (
                dob
                .replace("-", "/")
                .replace(".", "/")
            )

        if user_dob:

            user_dob = (
                user_dob
                .replace("-", "/")
                .replace(".", "/")
            )

        # =====================================================
        # MATCHES
        # =====================================================
        aadhaar_match = (
            aadhaar == user.aadhaar_number
            if aadhaar and user.aadhaar_number
            else False
        )

        dob_match = False

        # =====================================================
        # FULL DOB MATCH
        # =====================================================
        if dob and user_dob:

            if len(dob) == 4:

                dob_match = (
                    dob in user_dob
                )

            else:

                dob_match = (
                    dob == user_dob
                )

        # =====================================================
        # FAILED REASONS
        # =====================================================
        failed_reasons = []

        if not aadhaar_match:

            failed_reasons.append(
                f"Aadhaar mismatch: "
                f"extracted '{aadhaar}', "
                f"expected "
                f"'{user.aadhaar_number}'"
            )

        if not dob_match:

            failed_reasons.append(
                f"DOB mismatch: "
                f"extracted '{dob}', "
                f"expected '{user_dob}'"
            )

        # =====================================================
        # MASK AADHAAR
        # =====================================================
        masked_aadhaar = None

        if aadhaar:

            masked_aadhaar = (
                f"XXXXXXXX{aadhaar[-4:]}"
            )

        return {

            "extracted": {

                "aadhaar_number": (
                    masked_aadhaar
                ),

                "dob": dob,
            },

            "comparison": {

                "aadhaar_match": (
                    aadhaar_match
                ),

                "dob_match": dob_match,

                "verified": (
                    aadhaar_match
                    and dob_match
                ),
            },

            "user_data": {

                "aadhaar_number": (
                    user.aadhaar_number
                ),

                "dob": user_dob,
            },

            "failed_reasons": (
                failed_reasons
            ),
        }