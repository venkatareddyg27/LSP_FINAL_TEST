from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.orm import (
    Session
)

from core.database import get_db
from core.dependencies import require_roles
from core.logger import logger

from models.Auth.user import User

from models.Loan_application.loan_application import (
    LoanApplication
)

router = APIRouter(
    prefix="/loan/disbursement",
    tags=["Loan Disbursement"]
)


# =====================================================
# CURRENT USER
# =====================================================
def get_current_user(
    current_user: User = Depends(
        require_roles("USER")
    ),
) -> User:

    return current_user


# =====================================================
# CURRENT ADMIN / LENDER
# =====================================================
def get_current_admin(
    current_user: User = Depends(
        require_roles(
            "ADMIN",
            "SUPER_ADMIN",
            "LENDER"
        )
    ),
) -> User:

    return current_user


# =====================================================
# USER DISBURSEMENT STATUS
# =====================================================
@router.get(
    "/my-status"
)
def get_my_disbursement_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):

    try:

        application = (

            db.query(LoanApplication)

            .filter(
                LoanApplication.user_profile_id
                == current_user.id
            )

            .order_by(
                LoanApplication.id.desc()
            )

            .first()
        )

        if not application:

            raise HTTPException(
                status_code=404,
                detail="No application found"
            )

        logger.info(
            f"[MY DISBURSEMENT STATUS] "
            f"user={current_user.id}, "
            f"app={application.id}"
        )

        return {

            "application_id":
                application.id,

            "reference_number":
                application.reference_number,

            "application_status":
                application.application_status,

            "current_step":
                application.current_step,

            "disbursement_status":
                application.payout_status,

            "disbursed_amount":
                float(
                    application.disbursed_amount or 0
                ),

            "message":
                (
                    "Loan disbursed successfully"
                    if application.payout_status == "SUCCESS"
                    else "Disbursement pending"
                )
        }

    except HTTPException:

        raise

    except Exception as e:

        logger.error(
            f"[DISBURSEMENT STATUS ERROR] "
            f"user={current_user.id}, "
            f"error={str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to fetch disbursement status"
        )


# =====================================================
# ADMIN/LENDER DISBURSEMENT STATUS
# =====================================================
@router.get(
    "/{application_id}/status"
)
def get_disbursement_status(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_admin
    ),
):

    try:

        application = (

            db.query(LoanApplication)

            .filter(
                LoanApplication.id
                == application_id
            )

            .first()
        )

        if not application:

            raise HTTPException(
                status_code=404,
                detail="Application not found"
            )

        logger.info(
            f"[DISBURSEMENT STATUS] "
            f"user={current_user.id}, "
            f"app={application.id}"
        )

        return {

            "application_id":
                application.id,

            "reference_number":
                application.reference_number,

            "application_status":
                application.application_status,

            "current_step":
                application.current_step,

            "disbursement_status":
                application.payout_status,

            "disbursed_amount":
                float(
                    application.disbursed_amount or 0
                ),

            "message":
                (
                    "Loan disbursed successfully"
                    if application.payout_status == "SUCCESS"
                    else "Disbursement pending"
                )
        }

    except HTTPException:

        raise

    except Exception as e:

        logger.error(
            f"[DISBURSEMENT STATUS ERROR] "
            f"user={current_user.id}, "
            f"app={application_id}, "
            f"error={str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to fetch disbursement status"
        )