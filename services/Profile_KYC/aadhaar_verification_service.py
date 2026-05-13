from datetime import (
    datetime,
    timezone,
    timedelta
)

from sqlalchemy.orm import Session

from fastapi import HTTPException
from datetime import (
    datetime,
    timezone,
    timedelta
)

from sqlalchemy.orm import Session

from fastapi import HTTPException

from models.Profile_KYC.attempt_tracker import (
    VerificationType
)

from repositories.Profile_KYC.user_repository import (
    UserRepository
)

from repositories.Profile_KYC.attempt_tracker_repository import (
    AttemptTrackerRepository
)

from repositories.Profile_KYC.kyc_aadhaar_verification_repository import (
    KYCAadhaarVerificationRepository
)

from repositories.Profile_KYC.dummy_pan_repository import (
    DummyPANRepository
)

from core.config import settings


class AadhaarVerificationService:

    @staticmethod
    def verify_aadhaar(
        db: Session,
        user_id: int
    ) -> dict:

        # =============================================
        # USER
        # =============================================
        user = (
            UserRepository.get_by_user_id(
                db,
                user_id
            )
        )

        if not user:

            raise HTTPException(
                404,
                "User not found"
            )

        # =============================================
        # PAN MUST BE VERIFIED FIRST
        # =============================================
        if user.pan_status != "VERIFIED":

            raise HTTPException(
                400,
                "Please complete PAN verification first"
            )

        # =============================================
        # ALREADY VERIFIED
        # =============================================
        if user.aadhaar_status == "VERIFIED":

            masked = (
                f"XXXXXXXX"
                f"{user.aadhaar_number[-4:]}"
            )

            return {

                "message": (
                    "Aadhaar already verified"
                ),

                "aadhaar_status": (
                    "VERIFIED"
                ),

                "masked_aadhaar": masked,

                "next_step": (
                    "Proceed to bank account verification"
                ),
            }

        # =============================================
        # AADHAAR NUMBER
        # =============================================
        aadhaar_number = (
            user.aadhaar_number
        )

        if (
            not aadhaar_number
            or not aadhaar_number.isdigit()
            or len(aadhaar_number) != 12
        ):

            raise HTTPException(
                400,
                "Invalid Aadhaar number in profile"
            )

        # =============================================
        # ATTEMPT TRACKER
        # =============================================
        tracker = (
            AttemptTrackerRepository
            .get_by_email_and_type(
                db,
                user.email,
                VerificationType.AADHAAR
            )
        )

        if not tracker:

            tracker = (
                AttemptTrackerRepository
                .create_tracker(
                    db,
                    user.email,
                    VerificationType.AADHAAR
                )
            )

        now = datetime.now(
            timezone.utc
        )

        # =============================================
        # LOCK CHECK
        # =============================================
        if (
            tracker.locked_until
            and tracker.locked_until > now
        ):

            raise HTTPException(
                423,
                (
                    "Aadhaar verification blocked. "
                    f"Try after "
                    f"{settings.AADHAAR_COOLDOWN_HOURS} "
                    f"hours."
                ),
            )

        # =============================================
        # RESET LOCK
        # =============================================
        if (
            tracker.locked_until
            and tracker.locked_until <= now
        ):

            (
                AttemptTrackerRepository
                .reset_attempts(
                    db,
                    tracker
                )
            )

        # =============================================
        # INCREMENT ATTEMPT
        # =============================================
        current_attempt = (
            AttemptTrackerRepository
            .increment_attempt(
                db,
                tracker
            )
        )

        # =============================================
        # MAX ATTEMPTS
        # =============================================
        if (
            current_attempt
            > settings.AADHAAR_MAX_ATTEMPTS
        ):

            (
                AttemptTrackerRepository
                .lock_tracker(
                    db,
                    tracker,
                    now + timedelta(
                        hours=settings
                        .AADHAAR_COOLDOWN_HOURS
                    )
                )
            )

            raise HTTPException(
                423,
                (
                    f"Maximum attempts "
                    f"({settings.AADHAAR_MAX_ATTEMPTS}) "
                    f"exceeded. "
                    f"Try after "
                    f"{settings.AADHAAR_COOLDOWN_HOURS} "
                    f"hours."
                ),
            )

        # =============================================
        # AADHAAR RECORD
        # =============================================
        aadhaar_record = (
            DummyPANRepository
            .get_by_aadhaar_number(
                db,
                aadhaar_number
            )
        )

        failure_reason = None

        # =============================================
        # VALIDATION
        # =============================================
        if not aadhaar_record:

            failure_reason = (
                "Aadhaar number "
                "not found in records"
            )

        elif aadhaar_record.dob != user.dob:

            failure_reason = (
                "Date of birth does not "
                "match Aadhaar records"
            )

        # =============================================
        # FAILURE
        # =============================================
        if failure_reason:

            if (
                current_attempt
                >= settings
                .AADHAAR_MAX_ATTEMPTS
            ):

                status = "BLOCKED"

                (
                    AttemptTrackerRepository
                    .lock_tracker(
                        db,
                        tracker,
                        now + timedelta(
                            hours=settings
                            .AADHAAR_COOLDOWN_HOURS
                        )
                    )
                )

                user.aadhaar_status = (
                    "BLOCKED"
                )

            else:

                status = "FAILED"

                user.aadhaar_status = (
                    "FAILED"
                )

            # =========================================
            # LOG FAILURE
            # =========================================
            (
                KYCAadhaarVerificationRepository
                .create_verification_log(
                    db=db,

                    user_id=user.user_id,

                    aadhaar_number=(
                        aadhaar_number
                    ),

                    dob_submitted=(
                        str(user.dob)
                    ),

                    verified_dob="",

                    dob_match=False,

                    status=status,

                    failure_reason=(
                        failure_reason
                    ),

                    attempt_number=(
                        current_attempt
                    ),
                )
            )

            UserRepository.update_user(
                db,
                user
            )

            remaining = (
                settings
                .AADHAAR_MAX_ATTEMPTS
                - current_attempt
            )

            if remaining > 0:

                raise HTTPException(
                    400,
                    (
                        f"{failure_reason}. "
                        f"{remaining} "
                        f"attempt(s) remaining."
                    )
                )

            raise HTTPException(
                423,
                (
                    f"{failure_reason}. "
                    f"Maximum attempts reached. "
                    f"Blocked for "
                    f"{settings.AADHAAR_COOLDOWN_HOURS} "
                    f"hours."
                ),
            )

        # =============================================
        # SUCCESS
        # =============================================
        user.aadhaar_status = "VERIFIED"

        user.aadhaar_locked = True

        user.dob_locked = True

        user.aadhaar_verified_at = now

        # =============================================
        # LOG SUCCESS
        # =============================================
        (
            KYCAadhaarVerificationRepository
            .create_verification_log(
                db=db,

                user_id=user.user_id,

                aadhaar_number=(
                    aadhaar_number
                ),

                dob_submitted=(
                    str(user.dob)
                ),

                verified_dob=(
                    str(user.dob)
                ),

                dob_match=True,

                status="VERIFIED",

                failure_reason=None,

                attempt_number=(
                    current_attempt
                ),
            )
        )

        # =============================================
        # RESET ATTEMPTS
        # =============================================
        (
            AttemptTrackerRepository
            .reset_attempts(
                db,
                tracker
            )
        )

        UserRepository.update_user(
            db,
            user
        )

        masked = (
            f"XXXXXXXX"
            f"{aadhaar_number[-4:]}"
        )

        # =============================================
        # RESPONSE
        # =============================================
        return {

            "message": (
                "Aadhaar verified successfully"
            ),

            "aadhaar_status": (
                user.aadhaar_status
            ),

            "masked_aadhaar": masked,

            "next_step": (
                "Proceed to bank account verification"
            ),}