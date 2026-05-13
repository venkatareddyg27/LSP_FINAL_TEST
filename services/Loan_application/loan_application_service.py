from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException
import logging

from models.Loan_application.loan_application import (
    LoanApplication
)

from models.Loan_application.loan_application_steps import (
    LoanApplicationStepTracker
)

from models.Profile_KYC.user_profile import (
    UserProfile
)

from core.enums import (
    LoanApplicationStatus,
    LoanApplicationStep,
    enum_value,
)

from core.reference_generator import (
    generate_loan_reference_number
)

from services.Loan_application.loan_application_validation import (
    validate_final_submission
)

from services.Loan_application.loan_application_lock_manager_service import (
    ApplicationLockManager
)

from schemas.Loan_application.loan_application import (
    LoanSubmitResponseSchema,
)

logger = logging.getLogger(__name__)


# =========================================================
# STEP FLOW
# =========================================================
STEP_FLOW = {
    "EMI_CALCULATED": "PURPOSE",
    "PURPOSE": "REFERENCES",
    "REFERENCES": "DECLARATION",
    "DECLARATION": "SUMMARY",
    "SUMMARY": "SUBMITTED",
}


def get_next_step(current_step: str):

    if not current_step:
        return None

    return STEP_FLOW.get(
        current_step.upper()
    )


# =========================================================
# GET OR CREATE TRACKER
# =========================================================
def get_or_create_tracker(
    db: Session,
    application: LoanApplication
):

    tracker = (
        db.query(LoanApplicationStepTracker)
        .filter(
            LoanApplicationStepTracker.application_id
            == application.id
        )
        .first()
    )

    if not tracker:

        tracker = LoanApplicationStepTracker(
            application_id=application.id,

            purpose_completed=False,
            references_completed=False,
            declaration_completed=False,

            current_step=enum_value(
                LoanApplicationStep.EMI_CALCULATED
            ),

            last_completed_step=None
        )

        db.add(tracker)

        db.commit()

        db.refresh(tracker)

    return tracker


# =========================================================
# STRICT STEP VALIDATION
# =========================================================
def validate_all_steps_completed(
    tracker: LoanApplicationStepTracker
):

    # ================================================
    # PURPOSE
    # ================================================
    if not tracker.purpose_completed:

        raise HTTPException(
            400,
            {"pending_step": "PURPOSE"}
        )

    # ================================================
    # REFERENCES
    # ================================================
    if not tracker.references_completed:

        raise HTTPException(
            400,
            {"pending_step": "REFERENCES"}
        )

    # ================================================
    # DECLARATION
    # ================================================
    if not tracker.declaration_completed:

        raise HTTPException(
            400,
            {"pending_step": "DECLARATION"}
        )

    # ================================================
    # SUMMARY
    # ================================================
    if (
        tracker.current_step
        != enum_value(
            LoanApplicationStep.SUMMARY
        )
    ):

        raise HTTPException(
            status_code=400,
            detail={
                "pending_step": "SUMMARY"
            }
        )


# =========================================================
# SERVICE
# =========================================================
class LoanApplicationService:

    # ---------------------------------------------------
    # ENSURE EDITABLE
    # ---------------------------------------------------
    @staticmethod
    def ensure_editable(application):

        if application.is_submitted:

            raise HTTPException(
                400,
                "Application already submitted"
            )

        if (
            application.application_status
            != enum_value(
                LoanApplicationStatus.DRAFT
            )
        ):

            raise HTTPException(
                400,
                "Application is locked"
            )

    # ---------------------------------------------------
    # GET APPLICATION
    # ---------------------------------------------------
    @staticmethod
    def get_application(
        db: Session,
        user_id: int
    ):

        application = (
            db.query(LoanApplication)
            .filter(
                LoanApplication.user_profile_id
                == user_id
            )
            .order_by(
                LoanApplication.id.desc()
            )
            .first()
        )

        if not application:

            raise HTTPException(
                404,
                "No application found for this user"
            )

        tracker = get_or_create_tracker(
            db,
            application
        )

        return {

            "application_id": application.id,

            "application_status": (
                application.application_status
            ),

            "reference_number": (
                application.reference_number
            ),

            "current_step": (
                application.current_step
            ),

            "approved_amount": (
                application.approved_amount
            ),

            "requested_tenure_months": (
                application.requested_tenure_months
            ),

            "interest_rate": (
                application.interest_rate
            ),

            "lender_name": (
                application.lender_name
            ),

            "lender_id": (
                application.lender_id
            ),

            "is_submitted": (
                application.is_submitted
            ),

            "last_completed_step": (
                tracker.last_completed_step
            )
        }

    # ---------------------------------------------------
    # APPLY LOAN
    # ---------------------------------------------------
    @staticmethod
    def apply_loan(
        db: Session,
        user_id: int
    ):

        # ===============================================
        # USER PROFILE
        # ===============================================
        profile = (
            db.query(UserProfile)
            .filter(
                UserProfile.user_id == user_id
            )
            .first()
        )

        if not profile:

            raise HTTPException(
                404,
                "User profile not found"
            )

        # ===============================================
        # EXISTING APPLICATION
        # ===============================================
        application = (
            db.query(LoanApplication)
            .filter(
                LoanApplication.user_profile_id
                == profile.user_id
            )
            .order_by(
                LoanApplication.id.desc()
            )
            .first()
        )

        if not application:

            raise HTTPException(
                404,
                "Loan application not found"
            )

        # ===============================================
        # LENDER VALIDATION
        # ===============================================
        if not application.lender_id:

            raise HTTPException(
                400,
                "Please select lender first"
            )

        # ===============================================
        # ALREADY SUBMITTED
        # ===============================================
        submitted_statuses = [

            enum_value(
                LoanApplicationStatus.SUBMITTED
            ),

            "APPROVED",
            "AGREEMENT_GENERATED",
            "ESIGN_COMPLETED",
            "DISBURSEMENT_INITIATED",
            "DISBURSED",
            "ACTIVE"
        ]

        if (
            application.application_status
            in submitted_statuses
        ):

            return {

                "application_id": application.id,

                "status": (
                    application.application_status
                ),

                "message": (
                    "Application already submitted"
                ),

                "next_step": (
                    application.current_step
                )
            }

        # ===============================================
        # GET TRACKER
        # ===============================================
        tracker = get_or_create_tracker(
            db,
            application
        )

        # ===============================================
        # MOVE TO PURPOSE STEP
        # ===============================================
        tracker.current_step = (
            enum_value(
                LoanApplicationStep.PURPOSE
            )
        )

        tracker.last_completed_step = (
            enum_value(
                LoanApplicationStep.EMI_CALCULATED
            )
        )

        application.current_step = (
            enum_value(
                LoanApplicationStep.PURPOSE
            )
        )

        application.application_status = (
            enum_value(
                LoanApplicationStatus.DRAFT
            )
        )

        db.commit()

        db.refresh(application)

        return {

            "application_id": application.id,

            "application_status": (
                application.application_status
            ),

            "next_step": "PURPOSE",

            "message": (
                "Proceed to loan purpose"
            )
        }

    # ---------------------------------------------------
    # SUBMIT APPLICATION
    # ---------------------------------------------------
    @staticmethod
    def submit_latest_application(
        db: Session,
        user_id: int,
        confirm: bool
    ):

        if not confirm:

            raise HTTPException(
                400,
                "Confirmation required"
            )

        profile = (
            db.query(UserProfile)
            .filter(
                UserProfile.user_id == user_id
            )
            .first()
        )

        if not profile:

            raise HTTPException(
                404,
                "User profile not found"
            )

        application = (
            db.query(LoanApplication)
            .filter(
                LoanApplication.user_profile_id
                == user_id,

                LoanApplication.application_status
                == enum_value(
                    LoanApplicationStatus.DRAFT
                )
            )
            .order_by(
                LoanApplication.id.desc()
            )
            .first()
        )

        if not application:

            raise HTTPException(
                400,
                "No draft application found"
            )

        tracker = get_or_create_tracker(
            db,
            application
        )

        # ===============================================
        # VALIDATIONS
        # ===============================================
        validate_all_steps_completed(
            tracker
        )

        validate_final_submission(
            db,
            application,
            tracker
        )

        # ===============================================
        # SUBMIT APPLICATION
        # ===============================================
        application.reference_number = (
            generate_loan_reference_number(db)
        )

        application.application_status = (
            enum_value(
                LoanApplicationStatus.SUBMITTED
            )
        )

        application.is_submitted = True

        application.current_step = (
            enum_value(
                LoanApplicationStep.SUBMITTED
            )
        )

        application.submitted_at = (
            datetime.now(timezone.utc)
        )

        # ===============================================
        # UPDATE TRACKER
        # ===============================================
        (
            db.query(
                LoanApplicationStepTracker
            )
            .filter(
                LoanApplicationStepTracker
                .application_id
                == application.id
            )
            .update({

                "current_step": enum_value(
                    LoanApplicationStep.SUBMITTED
                ),

                "last_completed_step": enum_value(
                    LoanApplicationStep.SUMMARY
                )
            })
        )

        # ===============================================
        # LOCK APPLICATION
        # ===============================================
        ApplicationLockManager.lock_application(
            application
        )

        db.commit()

        db.refresh(application)

        return LoanSubmitResponseSchema(

            reference_number=(
                application.reference_number
            ),

            message=(
                "Application submitted successfully"
            ),

            expected_decision_time="24 hours"
        )