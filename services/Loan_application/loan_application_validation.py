from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from models.Loan_application.loan_application_references import (
    LoanApplicationReference
)

from models.Loan_application.loan_application_steps import (
    LoanApplicationStepTracker
)

from models.Loan_application.loan_application import (
    LoanApplication
)

from core.enums import (
    LoanApplicationStatus,
    enum_value
)


def validate_final_submission(
    db: Session,
    application: LoanApplication,
    tracker: LoanApplicationStepTracker
):

    # =====================================================
    # 1️⃣ VALIDATE APPLICATION EXISTS
    # =====================================================
    if not application:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loan application not found"
        )

    # =====================================================
    # 2️⃣ ALLOW ONLY DRAFT APPLICATIONS
    # =====================================================
    allowed_status = enum_value(
        LoanApplicationStatus.DRAFT
    )

    if application.application_status != allowed_status:

        # Already submitted flow
        if application.application_status in [
            "SUBMITTED",
            "APPROVED",
            "AGREEMENT_GENERATED",
            "ESIGN_COMPLETED",
            "DISBURSED",
            "ACTIVE"
        ]:

            return True

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid application status: "
                f"{application.application_status}"
            )
        )

    # =====================================================
    # 3️⃣ VALIDATE STEP TRACKER
    # =====================================================
    if not tracker:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application tracker not found"
        )

    # =====================================================
    # 4️⃣ VALIDATE STEPS COMPLETION
    # =====================================================
    if not tracker.loan_details_completed:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "pending_step": "LOAN_DETAILS",
                "message": (
                    "Loan details not completed"
                )
            }
        )

    if not tracker.purpose_completed:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "pending_step": "PURPOSE",
                "message": (
                    "Loan purpose not completed"
                )
            }
        )

    if not tracker.references_completed:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "pending_step": "REFERENCES",
                "message": (
                    "References not completed"
                )
            }
        )

    if not tracker.declaration_completed:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "pending_step": "DECLARATION",
                "message": (
                    "Declaration not completed"
                )
            }
        )

    # =====================================================
    # 5️⃣ VALIDATE SUMMARY STEP
    # =====================================================
    if tracker.current_step != "SUMMARY":

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "pending_step": "SUMMARY",
                "message": (
                    "Please review application "
                    "before submission"
                )
            }
        )

    # =====================================================
    # 6️⃣ VALIDATE REFERENCES
    # =====================================================
    references = (
        db.query(LoanApplicationReference)
        .filter(
            LoanApplicationReference.application_id
            == application.id
        )
        .all()
    )

    if len(references) != 2:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exactly 2 references are required"
        )

    # =====================================================
    # 7️⃣ VALIDATE OTP VERIFICATION
    # =====================================================
    if not all(ref.is_verified for ref in references):

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "All references must be OTP verified"
            )
        )

    # =====================================================
    # FINAL SUCCESS
    # =====================================================
    return True