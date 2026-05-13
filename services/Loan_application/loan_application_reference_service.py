from sqlalchemy.orm import Session
from fastapi import HTTPException

from models.Loan_application.loan_application import (
    LoanApplication
)

from models.Loan_application.loan_application_references import (
    LoanApplicationReference
)

from models.Loan_application.loan_application_steps import (
    LoanApplicationStepTracker
)

from core.enums import (
    LoanApplicationStep,
    enum_value
)

from services.Loan_application.loan_application_service import (
    LoanApplicationService,
)


# =====================================================
# GET OR CREATE TRACKER
# =====================================================
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

            loan_details_completed=False,

            purpose_completed=False,

            references_completed=False,

            declaration_completed=False,

            current_step=enum_value(
                LoanApplicationStep
                .EMI_CALCULATED
            ),

            last_completed_step=None
        )

        db.add(tracker)

        db.commit()

        db.refresh(tracker)

    return tracker


# =====================================================
# REFERENCE SERVICE
# =====================================================
class LoanApplicationReferenceService:

    # =================================================
    # SAVE REFERENCES
    # =================================================
    @staticmethod
    def save_references_form(
        db: Session,
        user_id: int,

        ref1_name,
        ref1_mobile_number,
        ref1_relation_type,
        ref1_is_emergency_contact,

        ref2_name,
        ref2_mobile_number,
        ref2_relation_type,
        ref2_is_emergency_contact,
    ):

        # =============================================
        # GET ACTIVE APPLICATION
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
        # CHECK EDITABLE
        # =============================================
        LoanApplicationService.ensure_editable(
            application
        )

        # =============================================
        # TRACKER
        # =============================================
        tracker = get_or_create_tracker(
            db,
            application
        )

        # =============================================
        # PURPOSE VALIDATION
        # =============================================
        if not tracker.purpose_completed:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Complete purpose step "
                    "before adding references"
                )
            )

        # =============================================
        # STEP VALIDATION
        # =============================================
        current_step = (
            tracker.current_step or ""
        ).strip().upper()

        expected_step = (
            LoanApplicationStep
            .REFERENCES.value
        )

        if current_step != expected_step:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid step. "
                    f"Expected {expected_step}, "
                    f"got {current_step}"
                )
            )

        try:

            # =========================================
            # REMOVE OLD REFERENCES
            # =========================================
            (
                db.query(
                    LoanApplicationReference
                )
                .filter(
                    LoanApplicationReference
                    .application_id
                    == application.id
                )
                .delete()
            )

            # =========================================
            # CREATE REFERENCES
            # =========================================
            new_refs = [

                LoanApplicationReference(
                    application_id=application.id,

                    name=ref1_name,

                    mobile_number=(
                        ref1_mobile_number
                    ),

                    relation_type=(
                        ref1_relation_type
                    ),

                    is_emergency_contact=(
                        ref1_is_emergency_contact
                    ),

                    is_verified=False,

                    otp_verified=False
                ),

                LoanApplicationReference(
                    application_id=application.id,

                    name=ref2_name,

                    mobile_number=(
                        ref2_mobile_number
                    ),

                    relation_type=(
                        ref2_relation_type
                    ),

                    is_emergency_contact=(
                        ref2_is_emergency_contact
                    ),

                    is_verified=False,

                    otp_verified=False
                )
            ]

            db.add_all(new_refs)

            # =========================================
            # REFERENCES ADDED
            # BUT NOT VERIFIED YET
            # =========================================
            tracker.references_completed = False

            tracker.last_completed_step = (
                LoanApplicationStep
                .REFERENCES.value
            )

            # =========================================
            # STAY IN REFERENCES STEP
            # UNTIL OTP VERIFICATION
            # =========================================
            tracker.current_step = (
                LoanApplicationStep
                .REFERENCES.value
            )

            application.current_step = (
                LoanApplicationStep
                .REFERENCES.value
            )

            db.commit()

            for ref in new_refs:
                db.refresh(ref)

            return {

                "application_id": (
                    application.id
                ),

                "references": [
                    {
                        "id": ref.id,

                        "name": ref.name,

                        "mobile_number": (
                            ref.mobile_number
                        ),

                        "relation_type": (
                            ref.relation_type
                        ),

                        "is_emergency_contact": (
                            ref.is_emergency_contact
                        ),

                        "is_verified": (
                            ref.is_verified
                        )
                    }
                    for ref in new_refs
                ],

                "current_step": (
                    LoanApplicationStep
                    .REFERENCES.value
                ),

                "next_step": (
                    "VERIFY_REFERENCES"
                ),

                "message": (
                    "References saved successfully. "
                    "Please verify references."
                )
            }

        except Exception as e:

            import traceback

            traceback.print_exc()

            db.rollback()

            raise HTTPException(
                500,
                f"Failed to save references: "
                f"{str(e)}"
            )

    # =================================================
    # GET REFERENCES
    # =================================================
    @staticmethod
    def get_references(
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
                "No application found"
            )

        refs = (
            db.query(
                LoanApplicationReference
            )
            .filter(
                LoanApplicationReference
                .application_id
                == application.id
            )
            .all()
        )

        verified_count = sum(
            ref.is_verified
            for ref in refs
        )

        return {

            "application_id": (
                application.id
            ),

            "references": [
                {
                    "id": ref.id,

                    "name": ref.name,

                    "mobile_number": (
                        ref.mobile_number
                    ),

                    "relation_type": (
                        ref.relation_type
                    ),

                    "is_emergency_contact": (
                        ref.is_emergency_contact
                    ),

                    "is_verified": (
                        ref.is_verified
                    )
                }
                for ref in refs
            ] if refs else [],

            "total_references": len(refs),

            "verified_references": (
                verified_count
            ),

            "pending_verifications": (
                max(0, 2 - verified_count)
            ),

            "is_references_completed": (
                verified_count == 2
            ),

            "current_step": (
                application.current_step
            )
        }