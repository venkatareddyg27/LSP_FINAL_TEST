import os

from fastapi import HTTPException

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from models.Esign.agreements import Agreement
from models.Loan_application.loan_application import LoanApplication
from models.Profile_KYC.user_profile import UserProfile

from core.logger import logger
from core.exceptions import throw_error

from services.Esign.pdf_generator import PDFGenerator
from core.email_service import EmailService


class AgreementService:

    def __init__(self, pdf: PDFGenerator):

        self.pdf = pdf

        self.email_service = EmailService()

    # =====================================================
    # GENERATE / FETCH AGREEMENT
    # =====================================================
    def fetch_agreement_for_user(
        self,
        user_id: int,
        db: Session
    ):

        logger.info(
            f"[Agreement] Fetching for user_id={user_id}"
        )

        try:

            # -------------------------------------------------
            # GET USER PROFILE
            # -------------------------------------------------
            profile = (
                db.query(UserProfile)
                .filter(
                    UserProfile.user_id == user_id
                )
                .first()
            )

            if not profile:

                throw_error(
                    "User profile not found",
                    404
                )

            user_profile_id = profile.user_id

            # -------------------------------------------------
            # FETCH APPLICATION
            # -------------------------------------------------
            application = (

                db.query(LoanApplication)

                .filter(

                    LoanApplication.user_profile_id
                    == user_profile_id,

                    LoanApplication.application_status.in_([
                        "SUBMITTED",
                        "UNDER_REVIEW",
                        "APPROVED",
                        "AGREEMENT_GENERATED",
                        "ESIGN_COMPLETED",
                        "CLOSED"
                    ])
                )

                .order_by(
                    LoanApplication.id.desc()
                )

                .with_for_update()

                .first()
            )

            # -------------------------------------------------
            # DEBUG
            # -------------------------------------------------
            if not application:

                latest_application = (

                    db.query(LoanApplication)

                    .filter(
                        LoanApplication.user_profile_id
                        == user_profile_id
                    )

                    .order_by(
                        LoanApplication.id.desc()
                    )

                    .first()
                )

                print(
                    "LATEST APPLICATION:",
                    latest_application.id
                    if latest_application
                    else None
                )

                print(
                    "LATEST STATUS:",
                    latest_application.application_status
                    if latest_application
                    else "NO APPLICATION"
                )

                throw_error(
                    (
                        "No eligible application found. "
                        "Please complete approval first."
                    ),
                    404
                )

            application_id = application.id

            # -------------------------------------------------
            # CHECK EXISTING AGREEMENT
            # -------------------------------------------------
            existing = (

                db.query(Agreement)

                .filter(
                    Agreement.application_id
                    == application_id
                )

                .order_by(
                    Agreement.id.desc()
                )

                .first()
            )

            # =================================================
            # EXISTING AGREEMENT
            # =================================================
            if existing:

                logger.info(
                    f"[Agreement] Existing agreement "
                    f"found for app={application_id}"
                )

                return {

                    "exists": True,

                    "agreement_id": (
                        existing.id
                    ),

                    "loan_id": (
                        application_id
                    ),

                    "status": (
                        existing.esign_status
                    ),

                    "pdf_path": (
                        existing.agreement_pdf_path
                    ),

                    "signed_pdf_path": (
                        existing.signed_pdf_path
                    ),

                    "download_url": (
                        existing.signed_pdf_path
                        or
                        existing.agreement_pdf_path
                    ),

                    "message": (
                        "Agreement already exists"
                    )
                }

            # -------------------------------------------------
            # VERSIONING
            # -------------------------------------------------
            latest = (

                db.query(Agreement)

                .filter(
                    Agreement.application_id
                    == application_id
                )

                .order_by(
                    Agreement.version.desc()
                )

                .first()
            )

            new_version = (

                1

                if not latest

                else latest.version + 1
            )

            # -------------------------------------------------
            # BORROWER NAME
            # -------------------------------------------------
            borrower_name = (

                getattr(
                    profile,
                    "full_name",
                    None
                )

                or

                (
                    f"{getattr(profile, 'first_name', '')} "
                    f"{getattr(profile, 'last_name', '')}"
                ).strip()

                or

                getattr(
                    profile,
                    "name",
                    None
                )
            )

            if not borrower_name:

                borrower_name = (
                    f"User-{user_id}"
                )

            # -------------------------------------------------
            # INTEREST RATE
            # -------------------------------------------------
            interest_rate = getattr(
                application,
                "interest_rate",
                None
            )

            interest_rate = round(
                float(interest_rate or 0),
                2
            )

            # -------------------------------------------------
            # GENERATE PDF
            # -------------------------------------------------
            pdf_output = (

                self.pdf.generate_agreement(

                    application_id=application_id,

                    borrower_name=borrower_name,

                    loan_amount=(
                        application.approved_amount
                    ),

                    interest_rate=interest_rate,

                    is_signed=False
                )
            )

            file_path = pdf_output.get(
                "file_path"
            )

            if not file_path:

                throw_error(
                    "PDF generation failed",
                    500
                )

            file_hash = (
                self.pdf.generate_hash(
                    file_path
                )
            )

            # -------------------------------------------------
            # DEACTIVATE OLD AGREEMENTS
            # -------------------------------------------------
            (
                db.query(Agreement)

                .filter(
                    Agreement.application_id
                    == application_id
                )

                .update({
                    "is_active": False
                })
            )

            # -------------------------------------------------
            # SAVE AGREEMENT
            # -------------------------------------------------
            agreement = Agreement(

                application_id=application_id,

                user_id=user_id,

                version=new_version,

                agreement_pdf_path=file_path,

                agreement_file_name=(
                    os.path.basename(file_path)
                ),

                file_hash=file_hash,

                is_active=True,

                status="GENERATED",

                esign_status="INITIATED",

                provider="EMUDHRA",

                signed_pdf_path=None
            )

            db.add(agreement)

            # -------------------------------------------------
            # UPDATE APPLICATION STATUS
            # -------------------------------------------------
            application.application_status = (
                "AGREEMENT_GENERATED"
            )

            db.commit()

            db.refresh(agreement)

            logger.info(
                f"[Agreement] Generated successfully "
                f"for app={application_id}"
            )

            return {

                "exists": False,

                "agreement_id": (
                    agreement.id
                ),

                "loan_id": (
                    application_id
                ),

                "pdf_path": (
                    agreement.agreement_pdf_path
                ),

                "status": (
                    agreement.esign_status
                ),

                "signed_pdf_path": (
                    agreement.signed_pdf_path
                ),

                "download_url": (
                    agreement.signed_pdf_path
                    or
                    agreement.agreement_pdf_path
                ),

                "message": (
                    "Agreement generated successfully"
                )
            }

        # =====================================================
        # DB ERROR
        # =====================================================
        except SQLAlchemyError as db_err:

            import traceback

            traceback.print_exc()

            db.rollback()

            logger.error(
                f"[Agreement][DB ERROR]: "
                f"{str(db_err)}"
            )

            throw_error(
                (
                    "Database error while "
                    "generating agreement"
                ),
                500
            )

        # =====================================================
        # HTTP EXCEPTION
        # =====================================================
        except HTTPException:
            raise

        # =====================================================
        # GENERIC ERROR
        # =====================================================
        except Exception as e:

            import traceback

            traceback.print_exc()

            db.rollback()

            logger.error(
                f"[Agreement][ERROR]: "
                f"{str(e)}"
            )

            throw_error(
                (
                    "Internal server error: "
                    f"{str(e)}"
                ),
                500
            )

    # =====================================================
    # GET EXISTING AGREEMENT
    # =====================================================
    def get_existing_agreement(
        self,
        user_id: int,
        db: Session
    ):

        logger.info(
            f"[Agreement] Fetch existing "
            f"agreement user_id={user_id}"
        )

        try:

            # -------------------------------------------------
            # USER PROFILE
            # -------------------------------------------------
            profile = (

                db.query(UserProfile)

                .filter(
                    UserProfile.user_id == user_id
                )

                .first()
            )

            if not profile:

                return None

            user_profile_id = profile.user_id

            # -------------------------------------------------
            # APPLICATION
            # -------------------------------------------------
            application = (

                db.query(LoanApplication)

                .filter(

                    LoanApplication.user_profile_id
                    == user_profile_id,

                    LoanApplication.application_status.in_([
                        "SUBMITTED",
                        "UNDER_REVIEW",
                        "APPROVED",
                        "AGREEMENT_GENERATED",
                        "ESIGN_COMPLETED",
                        "CLOSED"
                    ])
                )

                .order_by(
                    LoanApplication.id.desc()
                )

                .first()
            )

            # -------------------------------------------------
            # DEBUG
            # -------------------------------------------------
            if not application:

                latest_application = (

                    db.query(LoanApplication)

                    .filter(
                        LoanApplication.user_profile_id
                        == user_profile_id
                    )

                    .order_by(
                        LoanApplication.id.desc()
                    )

                    .first()
                )

                print(
                    "LATEST APPLICATION:",
                    latest_application.id
                    if latest_application
                    else None
                )

                print(
                    "LATEST STATUS:",
                    latest_application.application_status
                    if latest_application
                    else "NO APPLICATION"
                )

                return None

            # -------------------------------------------------
            # AGREEMENT
            # -------------------------------------------------
            agreement = (

                db.query(Agreement)

                .filter(
                    Agreement.application_id
                    == application.id
                )

                .order_by(
                    Agreement.id.desc()
                )

                .first()
            )

            # -------------------------------------------------
            # NO AGREEMENT
            # -------------------------------------------------
            if not agreement:

                return {

                    "message":
                        "Agreement not generated yet",

                    "loan_id":
                        application.id
                }

            # -------------------------------------------------
            # DEBUG AGREEMENT
            # -------------------------------------------------
            print({
                "agreement_id": agreement.id,
                "status": agreement.status,
                "esign_status": agreement.esign_status,
                "is_active": agreement.is_active,
                "pdf_path": agreement.agreement_pdf_path,
                "signed_pdf_path": agreement.signed_pdf_path
            })

            # -------------------------------------------------
            # DOWNLOAD PATH
            # -------------------------------------------------
            download_path = (
                agreement.signed_pdf_path
                or
                agreement.agreement_pdf_path
            )

            # -------------------------------------------------
            # SEND EMAIL
            # -------------------------------------------------
            email_sent = False

            try:

                user_email = getattr(
                    profile,
                    "email",
                    None
                )

                if user_email:

                    self.email_service.send_email_with_attachment(

                        to_email=user_email,

                        subject="Loan Agreement Download",

                        body=(
                            f"Dear "
                            f"{getattr(profile, 'full_name', 'Customer')},\n\n"
                            f"Your loan agreement is attached.\n\n"
                            f"Thank you."
                        ),

                        attachment_path=download_path
                    )

                    email_sent = True

                    logger.info(
                        f"[Agreement] Agreement emailed "
                        f"to {user_email}"
                    )

            except Exception as email_error:

                logger.error(
                    f"[Agreement EMAIL ERROR]: "
                    f"{str(email_error)}"
                )

            # -------------------------------------------------
            # RETURN AGREEMENT
            # -------------------------------------------------
            return {

                "agreement_id": (
                    agreement.id
                ),

                "loan_id": (
                    application.id
                ),

                "status": (
                    agreement.esign_status
                ),

                "pdf_path": (
                    agreement.agreement_pdf_path
                ),

                "signed_pdf_path": (
                    agreement.signed_pdf_path
                ),

                "download_url": (
                    download_path
                ),

                "email_sent": (
                    email_sent
                ),

                "message": (
                    "Agreement downloaded "
                    "and emailed successfully"
                )
            }

        except HTTPException:
            raise

        except Exception as e:

            import traceback

            traceback.print_exc()

            db.rollback()

            logger.error(
                f"[Agreement GET ERROR]: "
                f"{str(e)}"
            )

            return None