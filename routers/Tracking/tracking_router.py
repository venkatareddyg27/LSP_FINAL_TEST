from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.orm import (
    Session,
    joinedload
)

from core.database import get_db
from core.dependencies import require_roles
from core.logger import logger

from services.Tracking.tracking_service import (
    TrackingService
)

from schemas.Tracking.loan_status_schema import (
    LoanStatusResponse
)

from schemas.Tracking.loan_timeline_schema import (
    LoanStatusHistoryItem
)

from models.Auth.user import User

from models.Loan_application.loan_application import (
    LoanApplication
)


router = APIRouter(
    prefix="/loan",
    tags=["Loan Tracking"]
)


# ====================================================
# GET USER OWN APPLICATION
# ====================================================
def get_user_application(
    db: Session,
    current_user: User
):

    application = (

        db.query(LoanApplication)

        .options(
            joinedload(
                LoanApplication.user_profile
            )
        )

        .join(
            LoanApplication.user_profile
        )

        .filter(
            LoanApplication.user_profile.has(
                user_id=current_user.id
            )
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

    return application


# ====================================================
# GET USER APPLICATION STATUS
# ====================================================
@router.get(
    "/my/status",
    response_model=LoanStatusResponse,
    operation_id="get_my_application_status"
)
def get_my_application_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("USER")
    )
):

    try:

        application = (
            get_user_application(
                db,
                current_user
            )
        )

        logger.info(
            f"[MY STATUS] "
            f"user={current_user.id}, "
            f"app={application.id}"
        )

        return (
            TrackingService
            .get_application_status(

                db=db,

                application_id=(
                    application.id
                ),

                user_id=current_user.id
            )
        )

    except HTTPException:

        raise

    except Exception as e:

        logger.error(
            f"[MY STATUS ERROR] "
            f"user={current_user.id}, "
            f"error={str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to fetch application status"
        )


# ====================================================
# ADMIN APPLICATION STATUS
# ====================================================
@router.get(
    "/application/{application_id}/status",
    response_model=LoanStatusResponse,
    operation_id="get_application_status"
)
def get_application_status(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "ADMIN",
            "SUPER_ADMIN"
        )
    )
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
            f"[ADMIN STATUS] "
            f"admin={current_user.id}, "
            f"app={application.id}"
        )

        return (
            TrackingService
            .get_application_status(

                db=db,

                application_id=(
                    application.id
                ),

                user_id=current_user.id
            )
        )

    except HTTPException:

        raise

    except Exception as e:

        logger.error(
            f"[STATUS ERROR] "
            f"admin={current_user.id}, "
            f"app={application_id}, "
            f"error={str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to fetch application status"
        )


# ====================================================
# ADMIN APPLICATION TIMELINE
# ====================================================
@router.get(
    "/application/{application_id}/timeline",
    response_model=list[
        LoanStatusHistoryItem
    ],
    operation_id="get_application_timeline"
)
def get_application_timeline(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "ADMIN",
            "SUPER_ADMIN"
        )
    )
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
            f"[TIMELINE] "
            f"admin={current_user.id}, "
            f"app={application.id}"
        )

        return (
            TrackingService
            .get_application_timeline(

                db=db,

                application_id=(
                    application.id
                ),

                user_id=current_user.id
            )
        )

    except HTTPException:

        raise

    except Exception as e:

        logger.error(
            f"[TIMELINE ERROR] "
            f"admin={current_user.id}, "
            f"app={application_id}, "
            f"error={str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to fetch application timeline"
        )