from sqlalchemy.orm import Session

from datetime import (
    datetime,
    timedelta,
    timezone
)

import random
import hashlib

from fastapi import HTTPException

from core.sms import send_sms_msg91
from core.config import settings

from models.Loan_application.loan_application import (
    LoanApplication
)

from models.Loan_application.loan_application_steps import (
    LoanApplicationStepTracker
)

from models.Loan_application.loan_application_references import (
    LoanApplicationReference
)

from repositories.Loan_application.loan_application_reference_repo import (
    LoanApplicationReferenceRepository
)

from core.enums import (
    LoanApplicationStep,
    enum_value
)


COOLDOWN_SECONDS = 30
OTP_EXPIRY_SECONDS = 300
MAX_ATTEMPTS = 3


class ReferenceOTPService:

    # =================================================
    # SEND OTP
    # =================================================
    @staticmethod
    def send_reference_otp(
        db: Session,
        user_id: int,
        mobile_number: str,
        client_ip: str
    ):

        # =============================================
        # APPLICATION
        # =============================================
        application = (
            db.query(LoanApplication)
            .filter(
                LoanApplication.user_profile_id
                == user_id,

                LoanApplication.is_submitted
                == False
            )
            .order_by(
                LoanApplication.id.desc()
            )
            .first()
        )

        if not application:

            raise HTTPException(
                404,
                "No active draft application found"
            )

        # =============================================
        # REFERENCES
        # =============================================
        references = (
            LoanApplicationReferenceRepository
            .get_by_application_id(
                db,
                application.id
            )
        )

        reference = next(
            (
                r for r in references
                if r.mobile_number
                == mobile_number
            ),
            None
        )

        if not reference:

            raise HTTPException(
                404,
                "Reference not found"
            )

        # =============================================
        # ALREADY VERIFIED
        # =============================================
        if reference.is_verified:

            return {
                "message": (
                    "Reference already verified"
                )
            }

        now = datetime.utcnow()

        # =============================================
        # COOLDOWN
        # =============================================
        if (
            reference.otp_last_sent_at
            and (
                now
                - reference.otp_last_sent_at
            ).total_seconds()
            < COOLDOWN_SECONDS
        ):

            raise HTTPException(
                400,
                "Wait before requesting OTP"
            )

        # =============================================
        # GENERATE OTP
        # =============================================
        otp_plain = str(
            random.randint(
                100000,
                999999
            )
        )

        hashed_otp = hashlib.sha256(
            otp_plain.encode()
        ).hexdigest()

        # =============================================
        # STORE OTP
        # =============================================
        reference.otp_hash = hashed_otp

        reference.otp_attempts = 0

        reference.otp_expires_at = (
            now
            + timedelta(
                seconds=OTP_EXPIRY_SECONDS
            )
        )

        reference.otp_last_sent_at = now

        db.commit()

        # =============================================
        # DEV MODE
        # =============================================
        if settings.ENV.lower() == "dev":

            print(
                f"\n📲 Reference OTP "
                f"for {mobile_number}: "
                f"{otp_plain}\n"
            )

        # =============================================
        # PROD MODE
        # =============================================
        else:

            try:

                send_sms_msg91(
                    mobile_number,
                    otp_plain
                )

            except Exception as e:

                raise HTTPException(
                    500,
                    f"Failed to send OTP: "
                    f"{str(e)}"
                )

        return {

            "mobile_number": mobile_number,

            "message": (
                "OTP sent successfully"
            )
        }

    # =================================================
    # VERIFY OTP
    # =================================================
    @staticmethod
    def verify_reference_otp(
        db: Session,
        user_id: int,
        otp_code: str,
        client_ip: str = None
    ):

        # =============================================
        # APPLICATION
        # =============================================
        application = (
            db.query(LoanApplication)
            .filter(
                LoanApplication.user_profile_id
                == user_id,

                LoanApplication.is_submitted
                == False
            )
            .order_by(
                LoanApplication.id.desc()
            )
            .first()
        )

        if not application:

            raise HTTPException(
                404,
                "No active draft application found"
            )

        # =============================================
        # REFERENCES
        # =============================================
        references = (
            LoanApplicationReferenceRepository
            .get_by_application_id(
                db,
                application.id
            )
        )

        if not references:

            raise HTTPException(
                404,
                "References not found"
            )

        now = datetime.utcnow()

        hashed_input = hashlib.sha256(
            otp_code.encode()
        ).hexdigest()

        matched_reference = None

        # =============================================
        # FIND MATCHING OTP
        # =============================================
        for reference in references:

            if reference.is_verified:
                continue

            if (
                not reference.otp_expires_at
                or reference.otp_expires_at
                < now
            ):
                continue

            if (
                reference.otp_attempts
                >= MAX_ATTEMPTS
            ):
                continue

            if reference.otp_hash == hashed_input:

                matched_reference = reference
                break

        # =============================================
        # INVALID OTP
        # =============================================
        if not matched_reference:

            for reference in references:

                if (
                    not reference.is_verified
                    and reference.otp_attempts
                    < MAX_ATTEMPTS
                ):

                    reference.otp_attempts += 1

            db.commit()

            raise HTTPException(
                400,
                "Invalid OTP"
            )

        # =============================================
        # SUCCESS
        # =============================================
        matched_reference.is_verified = True

        matched_reference.otp_verified = True

        matched_reference.otp_hash = None

        matched_reference.otp_attempts = 0

        matched_reference.otp_expires_at = None

        db.commit()

        db.refresh(matched_reference)

        if client_ip:

            print(
                f"✅ OTP verified "
                f"for reference "
                f"{matched_reference.id} "
                f"from IP "
                f"{client_ip}"
            )

        # =============================================
        # UPDATE FLOW
        # =============================================
        (
            ReferenceOTPService
            .update_application_step_if_references_verified(
                db,
                matched_reference.application_id
            )
        )

        return {

            "reference_id": (
                matched_reference.id
            ),

            "mobile_number": (
                matched_reference.mobile_number
            ),

            "verified": True,

            "verified_at": (
                datetime.now(timezone.utc)
            ),

            "message": (
                "Reference verified successfully"
            )
        }

    # =================================================
    # UPDATE STEP AFTER VERIFICATION
    # =================================================
    @staticmethod
    def update_application_step_if_references_verified(
        db: Session,
        application_id: int
    ):

        references = (
            LoanApplicationReferenceRepository
            .get_by_application_id(
                db,
                application_id
            )
        )

        if not references:
            return

        # =============================================
        # CHECK ALL VERIFIED
        # =============================================
        if all(
            ref.is_verified
            for ref in references
        ):

            tracker = (
                db.query(
                    LoanApplicationStepTracker
                )
                .filter_by(
                    application_id=application_id
                )
                .first()
            )

            if not tracker:
                return

            # =========================================
            # REFERENCES COMPLETED
            # =========================================
            tracker.references_completed = True

            tracker.last_completed_step = (
                enum_value(
                    LoanApplicationStep
                    .REFERENCES
                )
            )

            # =========================================
            # MOVE TO DECLARATION
            # =========================================
            tracker.current_step = (
                enum_value(
                    LoanApplicationStep
                    .DECLARATION
                )
            )

            application = db.get(
                LoanApplication,
                application_id
            )

            if application:

                application.current_step = (
                    enum_value(
                        LoanApplicationStep
                        .DECLARATION
                    )
                )

            db.commit()