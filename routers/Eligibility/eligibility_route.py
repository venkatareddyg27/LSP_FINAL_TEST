from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import require_roles
from core.logger import logger

from models.Auth.user import User

from services.Eligibility.eligibility_service import (
    EligibilityService,
    CREDIT_SCORE_TIERS
)

router = APIRouter(
    prefix="/eligibility",
    tags=["Loan Eligibility"]
)


@router.post(
    "/check",
    operation_id="check_loan_eligibility"
)
def check_loan_eligibility(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("USER")
    )
):

    try:

        logger.info(
            f"[ELIGIBILITY CHECK] "
            f"user={current_user.id}"
        )

        # ================================================
        # ONLY CHECK ELIGIBILITY
        # ================================================
        eligibility = (
            EligibilityService
            .check_eligibility(
                db=db,
                user=current_user
            )
        )

    except HTTPException:
        raise

    except ValueError as e:

        logger.warning(
            f"[ELIGIBILITY ERROR] "
            f"user={current_user.id}, "
            f"error={str(e)}"
        )

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception as e:

        import traceback

        traceback.print_exc()

        logger.error(
            f"[ELIGIBILITY FAILED] "
            f"user={current_user.id}, "
            f"error={str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Eligibility check failed: {str(e)}"
        )

    status = eligibility.eligibility_status

    # ================================================
    # REJECTED
    # ================================================
    if status == "REJECTED":

        return {
            "user_id": current_user.id,
            "eligibility_status": status,

            "failure_reason": (
                eligibility.failure_reason
            ),

            "credit_summary": {
                "current_score": (
                    eligibility.credit_score_used
                ),
                "bureau": (
                    eligibility.bureau_name
                ),
            },

            "credit_score_tiers": [
                {
                    "min_score": score,
                    "max_loan_amount": amount
                }
                for score, amount
                in CREDIT_SCORE_TIERS
            ],

            "message": (
                "You are not eligible "
                "for a loan."
            )
        }

    # ================================================
    # SUCCESS
    # ================================================
    approved_amount = float(
        eligibility.max_eligible_amount or 0
    )

    return {

        "user_id": current_user.id,

        "eligibility_status": status,

        "loan_offer": {
            "approved_amount": approved_amount,
        },

        "credit_summary": {
            "current_score": (
                eligibility.credit_score_used
            ),
            "bureau": (
                eligibility.bureau_name
            ),
        },

        # USER WILL SELECT LENDER NEXT
        "next_step": "SELECT_LENDER",

        "message": (
            "You are eligible. "
            "Please select lender and tenure."
        )
    }