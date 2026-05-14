from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import require_roles

from models.Auth.user import User

from models.Loan_application.loan_application import (
    LoanApplication
)

from schemas.Loan_application.loan_application import (
    LoanSubmitRequestSchema,
    LoanSubmitResponseSchema,
    LoanApplicationResponseSchema,
)

from services.Loan_application.loan_application_service import (
    LoanApplicationService,
)

router = APIRouter(
    prefix="/loan/application",
    tags=["Apply Loan Application"],
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
# CURRENT ADMIN
# =====================================================
def get_current_admin(
    current_user: User = Depends(
        require_roles(
            "ADMIN",
            "SUPER_ADMIN"
        )
    ),
) -> User:

    return current_user


# =====================================================
# APPLY LOAN
# =====================================================
@router.post("/apply")
def apply(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):

    return LoanApplicationService.apply_loan(
        db=db,
        user_id=current_user.id,
    )


# =====================================================
# GET CURRENT USER APPLICATION
# =====================================================
@router.get(
    "/me",
    response_model=LoanApplicationResponseSchema,
)
def get_my_application(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):

    return LoanApplicationService.get_application(
        db=db,
        user_id=current_user.id,
    )


# =====================================================
# GET APPLICATION BY APPLICATION ID (ADMIN)
# =====================================================
@router.get(
    "/{application_id}",
    response_model=LoanApplicationResponseSchema,
)
def get_application_by_id(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_admin
    ),
):

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

    # =============================================
    # RETURN FULL APPLICATION DETAILS
    # =============================================
    return LoanApplicationService.get_application(
        db=db,
        user_id=application.user_profile_id
    )


# =====================================================
# GET ALL APPLICATIONS (ADMIN)
# =====================================================
@router.get(
    "/admin/all",
    response_model=list[
        LoanApplicationResponseSchema
    ],
)
def get_all_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_admin
    ),
):

    applications = (
        db.query(LoanApplication)
        .order_by(
            LoanApplication.id.desc()
        )
        .all()
    )

    # =============================================
    # RETURN ENHANCED APPLICATION DETAILS
    # =============================================
    result = []

    for application in applications:

        data = (
            LoanApplicationService
            .get_application(
                db=db,
                user_id=application.user_profile_id
            )
        )

        result.append(data)

    return result


# =====================================================
# SUBMIT APPLICATION
# =====================================================
@router.post(
    "/submit",
    response_model=LoanSubmitResponseSchema,
)
def submit_application(
    payload: LoanSubmitRequestSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):

    return (
        LoanApplicationService
        .submit_latest_application(
            db=db,
            user_id=current_user.id,
            confirm=payload.confirm,
        )
    )