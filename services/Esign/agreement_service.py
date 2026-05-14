import os

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from models.Esign.agreements import Agreement
from models.Loan_application.loan_application import LoanApplication
from models.Profile_KYC.user_profile import UserProfile

from core.logger import logger
from core.exceptions import throw_error

from services.Esign.pdf_generator import PDFGenerator


class AgreementService:

    def __init__(self, pdf: PDFGenerator):
        self.pdf = pdf

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
                        "APPROVED",
                        "AGREEMENT_GENERATED",
                        "ESIGN_COMPLETED"
                    ])
                )

                .order_by(
                    LoanApplication.id.desc()
                )

                .with_for_update()

                .first()
            )

            if not application:

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
                    == application_id,

                    Agreement.is_active == True
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

                # =============================================
                # BLOCK UNSIGNED AGREEMENT
                # =============================================
                if (
                    str(
                        existing.esign_status
                    ).upper()
                    != "SIGNED"
                ):

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

                        "signed_pdf_path": None,

                        "message": (
                            "Please complete e-sign "
                            "before downloading agreement"
                        )
                    }

                # =============================================
                # SIGNED PDF REQUIRED
                # =============================================
                if not existing.signed_pdf_path:

                    throw_error(
                        "Signed agreement not available",
                        404
                    )

                # =============================================
                # RETURN SIGNED AGREEMENT
                # =============================================
                return {

                    "exists": True,

                    "agreement_id": (
                        existing.id
                    ),

                    "loan_id": (
                        application_id
                    ),

                    "pdf_path": (
                        existing.agreement_pdf_path
                    ),

                    "status": (
                        existing.esign_status
                    ),

                    "signed_pdf_path": (
                        existing.signed_pdf_path
                    ),
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
                    == application_id,

                    Agreement.is_active == True
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

                "signed_pdf_path": None,

                "message": (
                    "Agreement generated successfully. "
                    "Please complete e-sign to "
                    "download signed agreement."
                )
            }

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

        except Exception as e:

            import traceback

            traceback.print_exc()

            db.rollback()

            logger.error(
                f"[Agreement][ERROR]: "
                f"{str(e)}"
            )

            throw_error(
                str(e),
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
                        "APPROVED",
                        "AGREEMENT_GENERATED",
                        "ESIGN_COMPLETED"
                    ])
                )

                .order_by(
                    LoanApplication.id.desc()
                )

                .first()
            )

            if not application:

                return None

            # -------------------------------------------------
            # AGREEMENT
            # -------------------------------------------------
            agreement = (

                db.query(Agreement)

                .filter(

                    Agreement.application_id
                    == application.id,

                    Agreement.is_active == True
                )

                .first()
            )

            if not agreement:

                return None

            # =============================================
            # BLOCK UNSIGNED ACCESS
            # =============================================
            if (
                str(
                    agreement.esign_status
                ).upper()
                != "SIGNED"
            ):

                return {

                    "agreement_id": (
                        agreement.id
                    ),

                    "message": (
                        "Please complete e-sign "
                        "before downloading agreement"
                    ),

                    "status": (
                        agreement.esign_status
                    ),

                    "pdf_path": (
                        agreement.agreement_pdf_path
                    ),

                    "signed_pdf_path": None
                }

            # =============================================
            # SIGNED PDF REQUIRED
            # =============================================
            if not agreement.signed_pdf_path:

                return {

                    "agreement_id": (
                        agreement.id
                    ),

                    "message": (
                        "Signed agreement "
                        "not available"
                    ),

                    "status": (
                        agreement.esign_status
                    ),

                    "pdf_path": (
                        agreement.agreement_pdf_path
                    ),

                    "signed_pdf_path": None
                }

            # =============================================
            # RETURN SIGNED PDF
            # =============================================
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
                )
            }

        except Exception as e:

            import traceback

            traceback.print_exc()

            db.rollback()

            logger.error(
                f"[Agreement GET ERROR]: "
                f"{str(e)}"
            )

            return None