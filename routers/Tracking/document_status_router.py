# routers/document_status_router.py

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

from models.Auth.user import User

from models.Loan_application.loan_application import (
    LoanApplication
)

from services.Tracking.document_status_service import (
    DocumentStatusService
)


router = APIRouter(
    prefix="/applications",
    tags=["Application Tracking"]
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
# USER DOCUMENT STATUS
# ====================================================
@router.get(
    "/my/document-status"
)
def get_my_document_status(
    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_roles("USER")
    )
):
    """
    USER → own application document status
    """

    try:

        application = (
            get_user_application(
                db,
                current_user
            )
        )

        logger.info(
            f"[MY DOC STATUS] "
            f"user={current_user.id}, "
            f"app={application.id}"
        )

        result = (
            DocumentStatusService
            .get_document_status(
                db,
                application
            )
        )

        return result

    except HTTPException:

        raise

    except Exception as e:

        logger.error(
            f"[MY DOC STATUS ERROR] "
            f"user={current_user.id}, "
            f"error={str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to fetch document status"
        )


# ====================================================
# ADMIN DOCUMENT STATUS
# ====================================================
@router.get(
    "/{application_id}/document-status"
)
def get_document_status(
    application_id: int,
    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_roles(
            "ADMIN",
            "SUPER_ADMIN"
        )
    )
):
    """
    ADMIN → any application document status
    """

    try:

        logger.info(
            f"[DOC STATUS REQUEST] "
            f"admin={current_user.id}, "
            f"app={application_id}"
        )

        # =============================================
        # FETCH APPLICATION
        # =============================================
        application = (

            db.query(LoanApplication)

            .options(
                joinedload(
                    LoanApplication.user_profile
                )
            )

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

        # =============================================
        # GET DOCUMENT STATUS
        # =============================================
        result = (
            DocumentStatusService
            .get_document_status(
                db,
                application
            )
        )

        logger.info(
            f"[DOC STATUS SUCCESS] "
            f"admin={current_user.id}, "
            f"app={application_id}"
        )

        return result

    except HTTPException:

        raise

    except Exception as e:

        logger.error(
            f"[DOC STATUS ERROR] "
            f"admin={current_user.id}, "
            f"app={application_id}, "
            f"error={str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to fetch document status"
        )