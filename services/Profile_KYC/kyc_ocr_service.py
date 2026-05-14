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
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


class KYCService:

    # =========================================================================
    # PDF DIRECT TEXT EXTRACTION
    # =========================================================================
    @staticmethod
    def _extract_text_from_pdf_direct(path: str) -> str:

        try:
            import fitz

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

        try:
            import fitz
        except ImportError:
            raise Exception(
                "PyMuPDF not installed. Run: pip install pymupdf"
            )

        doc = fitz.open(path)

        if len(doc) > 20:
            raise Exception("PDF exceeds maximum 20 pages")

        images = []

        for i, page in enumerate(doc):
            if i >= 2:
                break

            mat = fitz.Matrix(1.5, 1.5)

            pix = page.get_pixmap(
                matrix=mat,
                colorspace=fitz.csGRAY,
            )

            arr = np.frombuffer(
                pix.samples, dtype=np.uint8
            ).reshape(pix.height, pix.width)

            images.append(arr)

        doc.close()

        return images

    # =========================================================================
    # IMAGE PREPROCESS
    # =========================================================================
    @staticmethod
    def _preprocess_gray(gray: np.ndarray) -> np.ndarray:

        h, w = gray.shape[:2]

        if w < 900:
            scale = 900 / w
            gray  = cv2.resize(
                gray, None,
                fx=scale, fy=scale,
                interpolation=cv2.INTER_CUBIC,
            )

        gray = cv2.fastNlMeansDenoising(gray, h=10)

        thresh = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31, 10,
        )

        if thresh is None or thresh.size == 0:
            raise Exception("Invalid image after preprocessing")

        return thresh

    # =========================================================================
    # TEXT EXTRACTION
    # =========================================================================
    @staticmethod
    def extract_text(path: str, lang: str = "eng") -> str:

        if not os.path.exists(path):
            raise Exception(f"File not found: {path}")

        ext = os.path.splitext(path)[1].lower()

        if ext not in [".pdf", ".jpg", ".jpeg", ".png"]:
            raise Exception(f"Unsupported file type: {ext}")

        # ── PDF ───────────────────────────────────────────────────
        if ext == ".pdf":

            direct_text = KYCService._extract_text_from_pdf_direct(path)

            if direct_text and len(direct_text) > 50:
                print("========== OCR TEXT ==========")
                print(direct_text[:3000])
                print("================================")
                return direct_text

            pages    = KYCService._pdf_to_images(path)
            all_text = []

            for gray in pages:
                thresh = KYCService._preprocess_gray(gray)
                text   = pytesseract.image_to_string(
                    thresh,
                    lang   = lang,
                    config = (
                        "--oem 3 --psm 6 "
                        "-c preserve_interword_spaces=1"
                    ),
                    timeout = 20,
                )
                all_text.append(text)

            final_text = "\n".join(all_text)

            print("========== OCR TEXT ==========")
            print(final_text[:3000])
            print("================================")

            return final_text

        # ── Image ─────────────────────────────────────────────────
        img = cv2.imread(path)

        if img is None:
            raise Exception(f"Image not readable: {path}")

        h, w = img.shape[:2]

        if w < 900:
            scale = 900 / w
            img   = cv2.resize(
                img, None,
                fx=scale, fy=scale,
                interpolation=cv2.INTER_CUBIC,
            )

        gray   = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray   = cv2.fastNlMeansDenoising(gray, h=10)

        thresh = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31, 10,
        )

        if thresh is None or thresh.size == 0:
            raise Exception("Invalid image after preprocessing")

        text = pytesseract.image_to_string(
            thresh,
            lang   = lang,
            config = (
                "--oem 3 --psm 6 "
                "-c preserve_interword_spaces=1"
            ),
            timeout = 20,
        )

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
            r'(\d{2})[/\-\.](\d{2})[/\-\.](\d{4})', s
        )
        if m:
            return f"{m.group(1)}/{m.group(2)}/{m.group(3)}"

        return None

    # =========================================================================
    # PAN PROCESSING
    # =========================================================================
    @staticmethod
    def process_pan(text: str, user) -> dict:

        lines = [
            l.strip()
            for l in text.splitlines()
            if l.strip()
        ]

        pan = None

        for line in lines:
            m = re.search(r'\b([A-Z]{5}[0-9]{4}[A-Z])\b', line)
            if m:
                pan = m.group(1)
                break

        excluded_words = [
            "INCOME TAX", "DEPARTMENT", "GOVT", "GOVERNMENT",
            "INDIA", "FATHER", "SIGNATURE", "PERMANENT",
            "ACCOUNT", "CARD", "DATE", "BIRTH",
        ]

        candidate_names = []

        for line in lines:
            upper = line.upper()

            if re.search(r'[A-Z]{5}[0-9]{4}[A-Z]', upper):
                continue
            if re.search(r'\d', upper):
                continue
            if any(word in upper for word in excluded_words):
                continue

            cleaned = re.sub(r'[^A-Za-z\s]', '', line).strip()
            cleaned = re.sub(r'\s+', ' ', cleaned)

            if len(cleaned) >= 5:
                candidate_names.append(cleaned)

        extracted_name = ""
        best_score     = 0

        for candidate in candidate_names:
            _, score = KYCService.name_match(user.full_name, candidate)
            if score > best_score:
                best_score     = score
                extracted_name = candidate

        matched   = best_score >= 80
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
                f"expected '{user.pan_number}'"
            )

        if not matched:
            failed_reasons.append(
                f"Name mismatch: "
                f"extracted '{extracted_name}', "
                f"expected '{user.full_name}' "
                f"(score: {round(best_score, 1)})"
            )

        masked_pan = None
        if pan:
            masked_pan = f"{pan[:5]}XXXX{pan[-1]}"

        return {
            "extracted": {
                "pan_number": masked_pan,
                "name":       extracted_name,
            },
            "comparison": {
                "pan_match":  pan_match,
                "name_match": matched,
                "name_score": round(best_score, 2),
                "verified":   pan_match and matched,
            },
            "user_data": {
                "pan_number": user.pan_number,
                "full_name":  user.full_name,
            },
            "failed_reasons": failed_reasons,
        }

    # =========================================================================
    # AADHAAR PROCESSING
    # Handles two real-world layouts:
    #   Layout A — letter / e-Aadhaar (name inside address block after "To")
    #   Layout B — physical card (Telugu name above English, number at bottom)
    # =========================================================================
    @staticmethod
    def process_aadhaar(text: str, user) -> dict:

        lines = [
            l.strip()
            for l in text.splitlines()
            if l.strip()
        ]

        # ─────────────────────────────────────────────────────────
        # AADHAAR NUMBER
        # Strategy:
        #   1. Try strict grouped patterns (4-4-4) first.
        #   2. Fall back to plain 12-digit pattern.
        #   3. Prefer a candidate that exactly matches the known
        #      user.aadhaar_number (strips spaces/hyphens before
        #      comparing) so OCR noise on other lines is ignored.
        #   4. Skip any line containing "VID" to avoid VID numbers.
        # ─────────────────────────────────────────────────────────
        aadhaar = None

        # Normalize stored Aadhaar for comparison
        known_aadhaar = (
            re.sub(r'[\s\-]', '', user.aadhaar_number)
            if user.aadhaar_number
            else None
        )

        _aadhaar_patterns = [
            r'\b(\d{4}[\s\-]\d{4}[\s\-]\d{4})\b',   # strict 4-4-4
            r'\b(\d{4}\s?\d{4}\s?\d{4})\b',           # flexible spaces
            r'(\d{4}[\s\-]?\d{4}[\s\-]?\d{4})',       # no-boundary fallback
            r'\b(\d{12})\b',                           # plain 12-digit (no separators)
        ]

        first_candidate = None  # fallback if no exact match found

        for line in lines:
            if re.search(r'\bVID\b', line, re.IGNORECASE):
                continue

            # Also skip lines that are clearly DOB / issue date lines
            if re.search(
                r'(?:DOB|Date\s+of\s+Birth|issued)',
                line, re.IGNORECASE
            ):
                continue

            for pat in _aadhaar_patterns:
                m = re.search(pat, line)
                if m:
                    candidate = re.sub(r'[\s\-]', '', m.group(1))
                    if len(candidate) == 12:
                        # Exact match with stored number → use immediately
                        if known_aadhaar and candidate == known_aadhaar:
                            aadhaar = candidate
                            break
                        # Save first valid 12-digit candidate as fallback
                        if first_candidate is None:
                            first_candidate = candidate
            if aadhaar:
                break

        # Use first candidate if no exact match was found
        if not aadhaar and first_candidate:
            aadhaar = first_candidate

        # ─────────────────────────────────────────────────────────
        # DOB — line-by-line, skip "issued" lines
        # Priority 1: explicit DOB / Date of Birth label
        # Priority 2: any DD/MM/YYYY on a non-issued line
        # Priority 3: year-only fallback (YOB for minors)
        # ─────────────────────────────────────────────────────────
        dob = None

        for line in lines:
            if re.search(r'\bissued\b', line, re.IGNORECASE):
                continue
            dob_m = re.search(
                r'(?:DOB|Date\s+of\s+Birth)[:\s/]*'
                r'(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})',
                line, re.IGNORECASE,
            )
            if dob_m:
                dob = dob_m.group(1)
                break

        if not dob:
            for line in lines:
                if re.search(r'\bissued\b', line, re.IGNORECASE):
                    continue
                m = re.search(
                    r'(\d{2})[/\-\.](\d{2})[/\-\.](\d{4})', line
                )
                if m:
                    dob = f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
                    break

        if not dob:
            full_text = " ".join(lines)
            yob = re.search(r'\b(19\d{2}|20\d{2})\b', full_text)
            if yob:
                dob = yob.group(1)

        if dob:
            dob = dob.replace("-", "/").replace(".", "/")

        # ─────────────────────────────────────────────────────────
        # NAME EXTRACTION
        # ─────────────────────────────────────────────────────────
        def _is_ascii_name(s: str) -> bool:
            try:
                s.encode('ascii')
            except UnicodeEncodeError:
                return False

            cleaned = re.sub(r'[^A-Za-z\s]', '', s).strip()

            _skip = {
                "GOVERNMENT", "INDIA", "AADHAAR", "UNIQUE",
                "IDENTIFICATION", "AUTHORITY", "FEMALE", "MALE",
                "OTHER", "DOB", "DATE", "BIRTH", "MOBILE", "VTC",
                "PO", "SUB", "DISTRICT", "STATE", "PIN", "CODE",
                "ENROLMENT", "REGISTRATION", "VID", "PROOF",
                "IDENTITY", "CITIZENSHIP", "AUTHENTICATION",
                "SCANNING", "OFFLINE", "XML", "ONLINE", "BHARATA",
                "ISSUED", "YOUR", "NEAR", "HOUSE",
            }

            words = cleaned.upper().split()

            if not words or len(cleaned) < 4:
                return False
            if any(w in _skip for w in words):
                return False
            if re.search(r'\d', s):
                return False

            return True

        extracted_name = ""
        best_score     = 0

        # ── Layout A: "To" sentinel ───────────────────────────────
        for idx, line in enumerate(lines):
            if re.fullmatch(r'To', line.strip(), re.IGNORECASE):
                for offset in range(1, 5):
                    if idx + offset >= len(lines):
                        break
                    candidate_line = lines[idx + offset]
                    if re.match(
                        r'(?:C/O|S/O|D/O|W/O|Near|House|Plot|'
                        r'Flat|Ward|VTC|PO|Sub|District|State'
                        r'|PIN|Mobile)',
                        candidate_line, re.IGNORECASE,
                    ):
                        break
                    if _is_ascii_name(candidate_line):
                        candidate = re.sub(
                            r'[^A-Za-z\s]', '', candidate_line
                        ).strip()
                        _, score = KYCService.name_match(
                            user.full_name, candidate
                        )
                        if score > best_score:
                            best_score     = score
                            extracted_name = candidate
                break

        # ── Layout B: line before DOB / FEMALE / MALE ────────────
        if best_score < 60:
            dob_marker = re.compile(
                r'(?:DOB|FEMALE|MALE|OTHER|'
                r'\d{2}[/\-]\d{2}[/\-]\d{4})',
                re.IGNORECASE,
            )
            for idx, line in enumerate(lines):
                if dob_marker.search(line) and idx > 0:
                    for back in range(1, 4):
                        if idx - back < 0:
                            break
                        prev = lines[idx - back]
                        if _is_ascii_name(prev):
                            candidate = re.sub(
                                r'[^A-Za-z\s]', '', prev
                            ).strip()
                            _, score = KYCService.name_match(
                                user.full_name, candidate
                            )
                            if score > best_score:
                                best_score     = score
                                extracted_name = candidate
                            break
                    break

        # ── Fuzzy fallback ────────────────────────────────────────
        if best_score < 60:
            _skip_kw = {
                "GOVERNMENT", "INDIA", "AADHAAR", "UNIQUE",
                "IDENTIFICATION", "AUTHORITY", "BHARATA",
                "FEMALE", "MALE", "OTHER", "ENROLMENT",
                "REGISTRATION", "VID", "MOBILE", "DISTRICT",
                "STATE", "PROOF", "IDENTITY", "CITIZENSHIP",
                "AUTHENTICATION", "SCANNING", "OFFLINE",
            }
            for line in lines:
                if not _is_ascii_name(line):
                    continue
                upper = line.upper()
                if any(kw in upper for kw in _skip_kw):
                    continue
                candidate = re.sub(
                    r'[^A-Za-z\s]', '', line
                ).strip()
                candidate = re.sub(r'\s+', ' ', candidate)
                if len(candidate) < 4:
                    continue
                _, score = KYCService.name_match(
                    user.full_name, candidate
                )
                if score > best_score:
                    best_score     = score
                    extracted_name = candidate

        # ─────────────────────────────────────────────────────────
        # NORMALIZE USER DOB
        # ─────────────────────────────────────────────────────────
        user_dob = KYCService._normalize_dob(user.dob)
        if user_dob:
            user_dob = user_dob.replace("-", "/").replace(".", "/")

        # ─────────────────────────────────────────────────────────
        # MATCHES
        # ─────────────────────────────────────────────────────────
        aadhaar_match = (
            aadhaar == known_aadhaar
            if aadhaar and known_aadhaar
            else False
        )

        dob_match = False
        if dob and user_dob:
            if len(dob) == 4:
                dob_match = dob in user_dob
            else:
                dob_match = dob == user_dob

        name_match_result = best_score >= 80

        # ─────────────────────────────────────────────────────────
        # FAILED REASONS
        # ─────────────────────────────────────────────────────────
        failed_reasons = []

        if not aadhaar_match:
            failed_reasons.append(
                f"Aadhaar mismatch: "
                f"extracted '{aadhaar}', "
                f"expected '{user.aadhaar_number}'"
            )

        if not dob_match:
            failed_reasons.append(
                f"DOB mismatch: "
                f"extracted '{dob}', "
                f"expected '{user_dob}'"
            )

        if not name_match_result:
            failed_reasons.append(
                f"Name mismatch: "
                f"extracted '{extracted_name}', "
                f"expected '{user.full_name}' "
                f"(score: {round(best_score, 1)})"
            )

        masked_aadhaar = None
        if aadhaar:
            masked_aadhaar = f"XXXXXXXX{aadhaar[-4:]}"

        return {
            "extracted": {
                "aadhaar_number": masked_aadhaar,
                "name":           extracted_name,
                "dob":            dob,
            },
            "comparison": {
                "aadhaar_match": aadhaar_match,
                "dob_match":     dob_match,
                "name_match":    name_match_result,
                "name_score":    round(best_score, 2),
                "verified": (
                    aadhaar_match
                    and dob_match
                    and name_match_result
                ),
            },
            "user_data": {
                "aadhaar_number": user.aadhaar_number,
                "full_name":      user.full_name,
                "dob":            user_dob,
            },
            "failed_reasons": failed_reasons,
        }

    # =========================================================================
    # SALARY SLIP PROCESSING
    # =========================================================================
    @staticmethod
    def process_salary_slip(text: str, user) -> dict:
        """
        Extract employee name from salary slip and fuzzy-match
        against user.full_name.
        Pass 1 — look for a labelled "Employee Name:" line.
        Pass 2 — fuzzy scan all non-numeric, non-keyword lines.
        """

        lines = [
            l.strip()
            for l in text.splitlines()
            if l.strip()
        ]

        name_label_pattern = re.compile(
            r'(?:employee\s*name|emp\s*name|name\s*of\s*employee'
            r'|worker\s*name|staff\s*name)[:\-\s]*(.+)',
            re.IGNORECASE,
        )

        extracted_name = ""
        best_score     = 0

        # ── Pass 1: labelled line ─────────────────────────────────
        for line in lines:
            m = name_label_pattern.search(line)
            if m:
                candidate = re.sub(
                    r'[^A-Za-z\s]', '', m.group(1)
                ).strip()
                if len(candidate) >= 3:
                    _, score = KYCService.name_match(
                        user.full_name, candidate
                    )
                    if score > best_score:
                        best_score     = score
                        extracted_name = candidate

        # ── Pass 2: fuzzy scan fallback ───────────────────────────
        if best_score < 80:
            excluded_keywords = {
                "SALARY", "SLIP", "PAY", "PERIOD", "COMPANY",
                "DEPARTMENT", "DESIGNATION", "EMPLOYEE", "EMP",
                "ID", "BASIC", "HRA", "ALLOWANCE", "BONUS",
                "GROSS", "NET", "DEDUCTION", "PF", "ESI", "TAX",
                "TOTAL", "AMOUNT", "MONTH", "DATE", "BANK",
                "ACCOUNT", "IFSC", "PAN",
            }
            for line in lines:
                upper = line.upper()
                if re.search(r'\d', upper):
                    continue
                if any(kw in upper for kw in excluded_keywords):
                    continue
                candidate = re.sub(
                    r'[^A-Za-z\s]', '', line
                ).strip()
                candidate = re.sub(r'\s+', ' ', candidate)
                if len(candidate) < 3:
                    continue
                _, score = KYCService.name_match(
                    user.full_name, candidate
                )
                if score > best_score:
                    best_score     = score
                    extracted_name = candidate

        matched        = best_score >= 80
        failed_reasons = []

        if not matched:
            failed_reasons.append(
                f"Name mismatch on salary slip: "
                f"extracted '{extracted_name}', "
                f"expected '{user.full_name}' "
                f"(score: {round(best_score, 1)})"
            )

        return {
            "extracted": {
                "name": extracted_name,
            },
            "comparison": {
                "name_match": matched,
                "name_score": round(best_score, 2),
                "verified":   matched,
            },
            "user_data": {
                "full_name": user.full_name,
            },
            "failed_reasons": failed_reasons,
        }

    # =========================================================================
    # BANK STATEMENT PROCESSING
    # =========================================================================
    @staticmethod
    def process_bank_statement(
        text: str,
        user,
        bank_record,        # KYCBankVerification ORM row or None
    ) -> dict:
        """
        Validate a bank statement PDF against the user's verified
        KYCBankVerification record.
        Checks:
          1. bank_record exists and status == 'VERIFIED'
          2. Account number found in OCR text matches
          3. Account holder name matches (fuzzy, score >= 80)
        """

        # ── No verified bank record ───────────────────────────────
        if bank_record is None:
            return {
                "extracted": {
                    "account_number":      None,
                    "account_holder_name": None,
                },
                "comparison": {
                    "bank_record_found": False,
                    "account_match":     False,
                    "name_match":        False,
                    "verified":          False,
                },
                "user_data": {
                    "account_number":      None,
                    "account_holder_name": None,
                },
                "failed_reasons": [
                    "No verified bank record found for this user. "
                    "Complete bank KYC verification first."
                ],
            }

        if str(bank_record.status).upper() != "VERIFIED":
            return {
                "extracted": {
                    "account_number":      None,
                    "account_holder_name": None,
                },
                "comparison": {
                    "bank_record_found": True,
                    "account_match":     False,
                    "name_match":        False,
                    "verified":          False,
                },
                "user_data": {
                    "account_number":      bank_record.account_number,
                    "account_holder_name": bank_record.account_holder_name,
                },
                "failed_reasons": [
                    f"Bank record status is "
                    f"'{bank_record.status}', not VERIFIED."
                ],
            }

        lines     = [
            l.strip()
            for l in text.splitlines()
            if l.strip()
        ]
        full_text = " ".join(lines)

        # ── Account number ────────────────────────────────────────
        extracted_account = None
        clean_known       = re.sub(
            r'[\s\-]', '', bank_record.account_number
        )

        if clean_known in re.sub(r'[\s\-]', '', full_text):
            extracted_account = clean_known
        else:
            m = re.search(r'\b(\d{9,18})\b', full_text)
            if m:
                extracted_account = m.group(1)

        account_match = (
            extracted_account is not None
            and re.sub(r'[\s\-]', '', extracted_account) == clean_known
        )

        # ── Account holder name ───────────────────────────────────
        name_label_pattern = re.compile(
            r'(?:account\s*holder|account\s*name'
            r'|name\s*of\s*account|customer\s*name'
            r'|a[/]c\s*name|acc(?:ount)?\s*holder'
            r')[:\-\s]*(.+)',
            re.IGNORECASE,
        )

        extracted_name = ""
        best_score     = 0

        for line in lines:
            m = name_label_pattern.search(line)
            if m:
                candidate = re.sub(
                    r'[^A-Za-z\s]', '', m.group(1)
                ).strip()
                if len(candidate) >= 3:
                    _, score = KYCService.name_match(
                        bank_record.account_holder_name, candidate
                    )
                    if score > best_score:
                        best_score     = score
                        extracted_name = candidate

        if best_score < 80:
            for line in lines:
                if re.search(r'\d', line):
                    continue
                candidate = re.sub(
                    r'[^A-Za-z\s]', '', line
                ).strip()
                candidate = re.sub(r'\s+', ' ', candidate)
                if len(candidate) < 3:
                    continue
                _, score = KYCService.name_match(
                    bank_record.account_holder_name, candidate
                )
                if score > best_score:
                    best_score     = score
                    extracted_name = candidate

        name_match_result = best_score >= 80

        failed_reasons = []

        if not account_match:
            failed_reasons.append(
                f"Account number mismatch: "
                f"extracted '{extracted_account}', "
                f"expected '{bank_record.account_number}'"
            )

        if not name_match_result:
            failed_reasons.append(
                f"Account holder name mismatch: "
                f"extracted '{extracted_name}', "
                f"expected '{bank_record.account_holder_name}' "
                f"(score: {round(best_score, 1)})"
            )

        verified = account_match and name_match_result

        masked = None
        if extracted_account:
            masked = (
                "X" * (len(extracted_account) - 4)
                + extracted_account[-4:]
            )

        return {
            "extracted": {
                "account_number":      masked,
                "account_holder_name": extracted_name,
            },
            "comparison": {
                "bank_record_found": True,
                "account_match":     account_match,
                "name_match":        name_match_result,
                "name_score":        round(best_score, 2),
                "verified":          verified,
            },
            "user_data": {
                "account_number":      bank_record.account_number,
                "account_holder_name": bank_record.account_holder_name,
            },
            "failed_reasons": failed_reasons,
        }