from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models.Esign.esign_session import (
    EsignSession,
    EsignStatus
)

from models.Esign.signed_documents import SignedDocument
from models.Esign.agreements import Agreement

from models.Loan_application.loan_application import (
    LoanApplication
)

from models.Profile_KYC.user_profile import UserProfile

from providers.factory import get_esign_provider

from core.exceptions import throw_error
from core.logger import logger
from core.enums import (
    PaymentModeEnum,
    LoanApplicationStatus
)

from utils.file_handler import FileHandler

from services.Esign.pdf_generator import (
    PDFGenerator
)


class EsignService:

    def __init__(self):

        self.file_handler = FileHandler()

    # =====================================================
    # INITIATE E-SIGN
    # =====================================================
    async def initiate_esign(
        self,
        db: Session,
        user_id: int
    ):

        logger.info(
            f"[E-SIGN INIT] user_id={user_id}"
        )

        # =================================================
        # FETCH LATEST VALID LOAN
        # =================================================
        loan = (

            db.query(
                LoanApplication
            )

            .join(UserProfile)

            .filter(

                UserProfile.user_id
                == user_id,

                LoanApplication.application_status.notin_([
                    LoanApplicationStatus.REJECTED
                ])
            )

            .order_by(
                LoanApplication.id.desc()
            )

            .first()
        )

        logger.info(
            f"[ESIGN LOAN] {loan}"
        )

        if not loan:

            throw_error(
                "No valid loan found for eSign",
                404
            )

        # =================================================
        # AADHAAR VALIDATION
        # =================================================
        if (

            not loan.user_profile

            or not getattr(
                loan.user_profile,
                "aadhaar_number",
                None
            )
        ):

            throw_error(
                "Aadhaar not available",
                400
            )

        aadhaar_number = (
            loan.user_profile.aadhaar_number
        )

        # =================================================
        # REMOVE OLD OTP SESSION
        # =================================================
        existing = (

            db.query(
                EsignSession
            )

            .filter(

                EsignSession.application_id
                == loan.id,

                EsignSession.status
                == EsignStatus.OTP_SENT
            )

            .first()
        )

        if existing:

            logger.warning(
                "[ESIGN RETRY] "
                f"deleting old session "
                f"txn={existing.transaction_id}"
            )

            db.delete(existing)

            db.commit()

        # =================================================
        # GET ACTIVE AGREEMENT
        # =================================================
        agreement_id = (
            self._get_active_agreement_id(
                db,
                loan.id
            )
        )

        provider = get_esign_provider()

        payload = {

            "loan_id": loan.id,

            "aadhaar_number": (
                aadhaar_number
            ),
        }

        # =================================================
        # PROVIDER INITIATE
        # =================================================
        try:

            provider_resp = (

                await provider.initiate_esign(
                    payload
                )
            )

        except Exception as exc:

            logger.error(
                f"[E-SIGN INIT ERROR] "
                f"{str(exc)}"
            )

            throw_error(
                "eSign provider unreachable",
                503
            )

        txn = (

            provider_resp.get(
                "transaction_id"
            )

            or

            provider_resp.get(
                "txn_id"
            )
        )

        if not txn:

            logger.error(
                f"[INVALID PROVIDER RESPONSE] "
                f"{provider_resp}"
            )

            throw_error(
                "Invalid provider response",
                502
            )

        # =================================================
        # SAVE SESSION
        # =================================================
        try:

            session = EsignSession(

                application_id=loan.id,

                agreement_id=agreement_id,

                user_id=user_id,

                transaction_id=txn,

                request_payload=payload,

                response_payload=provider_resp,

                status=EsignStatus.OTP_SENT,
            )

            db.add(session)

            db.commit()

        except IntegrityError:

            db.rollback()

            throw_error(
                "Duplicate transaction",
                409
            )

        return {

            "transaction_id": txn,

            "masked_aadhaar": (

                provider_resp.get(
                    "masked_aadhaar"
                )
            ),
        }

    # =====================================================
    # VERIFY OTP
    # =====================================================
    async def verify_esign(
        self,
        data,
        db: Session
    ):

        session = (

            db.query(
                EsignSession
            )

            .filter(
                EsignSession.transaction_id
                == data.transaction_id
            )

            .with_for_update()

            .first()
        )

        if not session:

            throw_error(
                "Invalid transaction ID",
                404
            )

        # =================================================
        # ALREADY SIGNED
        # =================================================
        if session.status == EsignStatus.SIGNED:

            return {
                "status": "SIGNED"
            }

        existing_signed = (

            db.query(
                EsignSession
            )

            .filter(

                EsignSession.agreement_id
                == session.agreement_id,

                EsignSession.status
                == EsignStatus.SIGNED
            )

            .with_for_update()

            .first()
        )

        if existing_signed:

            return {

                "status": "SIGNED",

                "message": "Already signed"
            }

        provider = get_esign_provider()

        # =================================================
        # VERIFY OTP
        # =================================================
        try:

            provider_resp = (

                await provider.verify_esign(
                    data.model_dump()
                )
            )

        except Exception as exc:

            logger.error(
                f"[VERIFY ERROR] "
                f"{str(exc)}"
            )

            throw_error(
                "OTP verification failed",
                503
            )

        # =================================================
        # INVALID OTP
        # =================================================
        if provider_resp.get("status") != "SIGNED":

            throw_error(
                "Invalid OTP",
                400
            )

        # =================================================
        # UPDATE SESSION
        # =================================================
        session.status = (
            EsignStatus.SIGNED
        )

        # =================================================
        # FETCH LOAN
        # =================================================
        loan = (

            db.query(
                LoanApplication
            )

            .filter(
                LoanApplication.id
                == session.application_id
            )

            .with_for_update()

            .first()
        )

        # =================================================
        # UPDATE AGREEMENT
        # =================================================
        agreement = (

            db.query(
                Agreement
            )

            .filter(
                Agreement.id
                == session.agreement_id
            )

            .with_for_update()

            .first()
        )

        if agreement and loan:

            # =============================================
            # BORROWER NAME
            # =============================================
            borrower_name = "Borrower"

            if loan.user_profile:

                borrower_name = (

                    getattr(
                        loan.user_profile,
                        "full_name",
                        None
                    )

                    or

                    (
                        f"{getattr(loan.user_profile, 'first_name', '')} "
                        f"{getattr(loan.user_profile, 'last_name', '')}"
                    ).strip()

                    or "Borrower"
                )

            # =============================================
            # GENERATE SIGNED PDF
            # =============================================
            pdf_generator = PDFGenerator()

            signed_pdf = (

                pdf_generator.generate_agreement(

                    application_id=loan.id,

                    borrower_name=borrower_name,

                    loan_amount=(
                        loan.approved_amount
                    ),

                    interest_rate=(
                        loan.interest_rate
                    ),

                    is_signed=True,

                    signed_at=datetime.utcnow().strftime(
                        "%d-%m-%Y %H:%M:%S UTC"
                    )
                )
            )

            signed_file_path = (
                signed_pdf.get(
                    "file_path"
                )
            )

            signed_hash = (
                pdf_generator.generate_hash(
                    signed_file_path
                )
            )

            # =============================================
            # UPDATE AGREEMENT
            # =============================================
            agreement.esign_status = (
                "SIGNED"
            )

            agreement.signed_pdf_path = (
                signed_file_path
            )

            agreement.file_hash = (
                signed_hash
            )

            # =============================================
            # SAVE SIGNED DOCUMENT
            # =============================================
            db.add(

                SignedDocument(

                    session_id=session.id,

                    agreement_id=session.agreement_id,

                    application_id=session.application_id,

                    signed_pdf_path=signed_file_path,

                    file_hash=signed_hash,
                )
            )

        # =================================================
        # UPDATE LOAN STATUS
        # =================================================
        if loan:

            loan.application_status = (
                "ESIGN_COMPLETED"
            )

        db.commit()

        logger.info(
            f"[ESIGN SUCCESS] "
            f"application={session.application_id}"
        )

        return {
            "status": "SIGNED"
        }

    # =====================================================
    # CALLBACK HANDLER
    # =====================================================
    async def handle_callback(
        self,
        data,
        db: Session
    ):

        logger.info(
            f"[CALLBACK] "
            f"txn={data.transaction_id}"
        )

        loan = None

        try:

            session = (

                db.query(
                    EsignSession
                )

                .filter(
                    EsignSession.transaction_id
                    == data.transaction_id
                )

                .with_for_update()

                .first()
            )

            if not session:

                throw_error(
                    "Unknown transaction ID",
                    404
                )

            if session.status == EsignStatus.SIGNED:

                return {
                    "status": "already_processed"
                }

            if data.status != "SIGNED":

                session.status = (
                    EsignStatus.FAILED
                )

                db.commit()

                throw_error(
                    "Signing failed",
                    400
                )

            session.callback_payload = (
                data.model_dump()
            )

            db.commit()

        except Exception as e:

            import traceback

            db.rollback()

            traceback.print_exc()

            logger.error(
                f"[CALLBACK ERROR] "
                f"{str(e)}"
            )

            throw_error(
                f"Callback processing failed: "
                f"{str(e)}",
                500
            )

        # =================================================
        # SAFE DISBURSEMENT
        # =================================================
        try:

            if (

                loan

                and loan.application_status
                == "ESIGN_COMPLETED"
            ):

                from services.Loan_application.loan_disbursement_service import (
                    LoanDisbursementService
                )

                LoanDisbursementService.disburse_loan(

                    db,

                    loan.id,

                    PaymentModeEnum.BANK,
                )

        except Exception as e:

            logger.error(
                f"[DISBURSE ERROR] "
                f"{str(e)}"
            )

        return {

            "status": "success",

            "application_id": (
                session.application_id
            ),
        }

    # =====================================================
    # GET ACTIVE AGREEMENT
    # =====================================================
    def _get_active_agreement_id(
        self,
        db: Session,
        application_id: int
    ):

        agreement = (

            db.query(
                Agreement
            )

            .filter(

                Agreement.application_id
                == application_id,

                Agreement.is_active == True
            )

            .first()
        )

        if not agreement:

            throw_error(
                "Active agreement not found",
                404
            )

        return agreement.id