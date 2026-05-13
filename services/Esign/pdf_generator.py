from pathlib import Path
import hashlib

from datetime import datetime

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from core.config import settings
from core.logger import logger


class PDFGenerator:

    def __init__(self):

        # =================================================
        # STORAGE DIRECTORY
        # =================================================
        self.output_dir: Path = Path(
            settings.AGREEMENT_STORAGE_PATH
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

    # =====================================================
    # GENERATE AGREEMENT PDF
    # =====================================================
    def generate_agreement(
        self,
        application_id: int,
        borrower_name: str,
        loan_amount: float,
        interest_rate: float,

        # ================================================
        # E-SIGN SUPPORT
        # ================================================
        is_signed: bool = False,
        signed_at: str = None
    ):

        # -------------------------------------------------
        # CLEAN VALUES
        # -------------------------------------------------
        borrower_name = (
            borrower_name
            or "N/A"
        )

        loan_amount = float(
            loan_amount or 0
        )

        interest_rate = round(
            float(interest_rate or 0),
            2
        )

        # -------------------------------------------------
        # FORMAT VALUES
        # -------------------------------------------------
        formatted_amount = (
            f"₹ {loan_amount:,.2f}"
        )

        formatted_rate = (
            f"{interest_rate:.2f}% per year"
        )

        formatted_date = (
            datetime.utcnow().strftime(
                "%d-%m-%Y %H:%M:%S UTC"
            )
        )

        # -------------------------------------------------
        # DIRECTORY
        # -------------------------------------------------
        loan_dir = (
            self.output_dir
            / str(application_id)
        )

        loan_dir.mkdir(
            exist_ok=True
        )

        timestamp = (
            datetime.utcnow().strftime(
                "%Y%m%d_%H%M%S"
            )
        )

        # -------------------------------------------------
        # FILE NAME
        # -------------------------------------------------
        if is_signed:

            file_name = (
                f"signed_agreement_"
                f"{application_id}_"
                f"{timestamp}.pdf"
            )

        else:

            file_name = (
                f"agreement_v"
                f"{timestamp}_"
                f"{application_id}.pdf"
            )

        file_path = (
            loan_dir / file_name
        )

        logger.info(
            f"[PDF] Generating agreement: "
            f"{file_path}"
        )

        # -------------------------------------------------
        # CREATE PDF
        # -------------------------------------------------
        c = canvas.Canvas(
            str(file_path),
            pagesize=LETTER
        )

        width, height = LETTER

        # =================================================
        # TITLE
        # =================================================
        c.setFont(
            "Helvetica-Bold",
            22
        )

        c.drawCentredString(
            width / 2,
            height - 60,
            "Loan Agreement Document"
        )

        # =================================================
        # GENERATED TIME
        # =================================================
        c.setFont(
            "Helvetica",
            10
        )

        c.drawString(
            50,
            height - 85,
            f"Generated On: "
            f"{formatted_date}"
        )

        # =================================================
        # BORROWER DETAILS
        # =================================================
        c.setFont(
            "Helvetica-Bold",
            14
        )

        c.drawString(
            50,
            height - 120,
            "Borrower Information"
        )

        c.setFont(
            "Helvetica",
            12
        )

        c.drawString(
            50,
            height - 145,
            f"Borrower Name: "
            f"{borrower_name}"
        )

        c.drawString(
            50,
            height - 165,
            f"Application ID: "
            f"{application_id}"
        )

        c.drawString(
            50,
            height - 185,
            f"Loan Amount: "
            f"{formatted_amount}"
        )

        c.drawString(
            50,
            height - 205,
            f"Interest Rate: "
            f"{formatted_rate}"
        )

        # =================================================
        # TERMS & CONDITIONS
        # =================================================
        terms = [

            "1. Loan must be repaid as per EMI schedule.",

            "2. Late payment penalty applies.",

            "3. Pre-closure allowed after 3 EMIs.",

            "4. Processing fee is non-refundable.",

            "5. This is a system-generated legal document.",

            "6. E-sign is legally valid under IT Act.",

            "7. Signed agreement is digitally verified."
        ]

        c.setFont(
            "Helvetica-Bold",
            14
        )

        c.drawString(
            50,
            height - 250,
            "Loan Terms & Conditions"
        )

        c.setFont(
            "Helvetica",
            11
        )

        y = height - 280

        for t in terms:

            c.drawString(
                60,
                y,
                t
            )

            y -= 18

        # =================================================
        # DIGITAL SIGNATURE SECTION
        # =================================================
        c.setFont(
            "Helvetica-Bold",
            12
        )

        if is_signed:

            signed_time = (

                signed_at

                or

                datetime.utcnow().strftime(
                    "%d-%m-%Y %H:%M:%S UTC"
                )
            )

            # ---------------------------------------------
            # DIGITAL SIGN LABEL
            # ---------------------------------------------
            c.drawString(
                50,
                180,
                "DIGITAL SIGNATURE DETAILS"
            )

            c.setFont(
                "Helvetica",
                11
            )

            c.drawString(
                50,
                155,
                f"Digitally Signed By: "
                f"{borrower_name}"
            )

            c.drawString(
                50,
                135,
                f"Signed On: "
                f"{signed_time}"
            )

            c.drawString(
                50,
                115,
                "Signature Status: VERIFIED "
            )

            c.drawString(
                50,
                95,
                "Authentication: Aadhaar OTP Based E-Sign"
            )

        else:

            # ---------------------------------------------
            # UNSIGNED TEMPLATE
            # ---------------------------------------------
            c.drawString(
                50,
                150,
                "Borrower Signature: ____________________________"
            )

        # =================================================
        # LENDER SIGNATURE
        # =================================================
        c.drawString(
            50,
            65,
            "Lender Authority Signature: _____________________"
        )

        # =================================================
        # FOOTER
        # =================================================
        c.setFont(
            "Helvetica",
            10
        )

        footer_text = (

            "This is a system-generated legal document."

            if not is_signed

            else

            "This document has been digitally signed and verified."
        )

        c.drawCentredString(
            width / 2,
            30,
            footer_text
        )

        # =================================================
        # SAVE PDF
        # =================================================
        c.showPage()

        c.save()

        logger.info(
            f"[PDF GENERATED SUCCESS] "
            f"{file_path}"
        )

        return {

            "file_path": str(file_path),

            "file_name": file_name
        }

    # =====================================================
    # HASH GENERATION
    # =====================================================
    def generate_hash(
        self,
        file_path: str
    ):

        sha256 = hashlib.sha256()

        with open(
            file_path,
            "rb"
        ) as f:

            for block in iter(
                lambda: f.read(4096),
                b""
            ):

                sha256.update(block)

        return sha256.hexdigest()