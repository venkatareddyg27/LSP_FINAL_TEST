from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status
)

from sqlalchemy.orm import Session
from sqlalchemy import func

from core.database import get_db

from models.Auth.lender import Lender
from models.Auth.user import User

from schemas.Auth.lenderregisterschema import (
    LenderCreate,
    LenderResponse,
    LenderUpdate
)

from services.Auth.superadminservices import (
    super_admin_required,
)

from core.security import hash_password

from core.validators import (
    validate_mobile_number,
    validate_password
)

router = APIRouter(
    prefix="/lenders",
    tags=["SuperAdmin Lenders"]
)

# ======================================================
# CREATE LENDER
# ======================================================
@router.post(
    "/create",
    response_model=LenderResponse,
    status_code=status.HTTP_201_CREATED,
    name="admin_create_lender"
)
def create_lender(
    lender_data: LenderCreate,
    db: Session = Depends(get_db),
    superadmin=Depends(super_admin_required),
):

    try:

        validate_mobile_number(
            lender_data.mobile_number
        )

        validate_password(
            lender_data.password
        )

        # =============================================
        # CHECK MOBILE
        # =============================================
        existing_user = db.query(User).filter(
            User.mobile_number
            == lender_data.mobile_number,
            User.role == "LENDER"
        ).first()

        if existing_user:

            raise HTTPException(
                status_code=400,
                detail="Mobile number already exists"
            )

        # =============================================
        # CHECK COMPANY NAME
        # =============================================
        existing_company = db.query(Lender).filter(
            func.lower(Lender.company_name)
            == lender_data.company_name.lower()
        ).first()

        if existing_company:

            raise HTTPException(
                status_code=400,
                detail="Company name already exists"
            )

        # =============================================
        # CHECK GST
        # =============================================
        existing_gst = db.query(Lender).filter(
            Lender.gst_number
            == lender_data.gst_number
        ).first()

        if existing_gst:

            raise HTTPException(
                status_code=400,
                detail="GST number already exists"
            )

        username = (
            lender_data.company_name
            .lower()
            .strip()
        )

        # =============================================
        # CREATE USER
        # =============================================
        user = User(

            mobile_number=(
                lender_data.mobile_number
            ),

            username=username,

            password_hash=hash_password(
                lender_data.password
            ),

            role="LENDER",

            device_id="lender-device",

            is_verified=True,

            is_active=True,
        )

        db.add(user)

        db.flush()

        # =============================================
        # CREATE LENDER
        # =============================================
        lender = Lender(

            user_id=user.id,

            company_name=(
                lender_data.company_name
            ),

            gst_number=(
                lender_data.gst_number
            ),

            address=(
                lender_data.address
            ),

            min_credit_score=(
                lender_data.min_credit_score
            ),

            max_amount=(
                lender_data.max_amount
            ),

            interest_rate=(
                lender_data.interest_rate
            ),

            processing_fee=(
                lender_data.processing_fee
            ),

            benefits=(
                lender_data.benefits
            ),

            created_by=superadmin.id,

            updated_by=superadmin.id,

            is_active=True,

            is_verified=True,

            is_blocked=False,
        )

        db.add(lender)

        db.commit()

        db.refresh(lender)

        return lender

    except HTTPException:
        raise

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# ======================================================
# UPDATE LENDER
# ======================================================
@router.put(
    "/update/{company_name}",
    response_model=LenderResponse,
    name="admin_update_lender"
)
def update_lender(
    company_name: str,
    lender_data: LenderUpdate,
    db: Session = Depends(get_db),
    superadmin=Depends(super_admin_required),
):

    try:

        lender = db.query(Lender).join(
            User,
            User.id == Lender.user_id
        ).filter(
            func.lower(Lender.company_name)
            == company_name.lower(),
            User.role == "LENDER"
        ).first()

        if not lender:

            raise HTTPException(
                status_code=404,
                detail="Lender not found"
            )

        update_data = lender_data.model_dump(
            exclude_unset=True
        )

        # =========================================
        # COMPANY NAME UPDATE
        # =========================================
        if "company_name" in update_data:

            new_name = (
                update_data["company_name"]
                .lower()
                .strip()
            )

            existing_company = db.query(Lender).filter(
                func.lower(Lender.company_name)
                == new_name,
                Lender.id != lender.id
            ).first()

            if existing_company:

                raise HTTPException(
                    status_code=400,
                    detail="Company name already exists"
                )

            lender.user.username = new_name

            lender.company_name = new_name

            update_data.pop("company_name")

        # =========================================
        # UPDATE FIELDS
        # =========================================
        for key, value in update_data.items():

            setattr(
                lender,
                key,
                value
            )

        lender.updated_by = superadmin.id

        db.commit()

        db.refresh(lender)

        return lender

    except HTTPException:
        raise

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# ======================================================
# DELETE LENDER
# ======================================================
@router.delete(
    "/delete/{company_name}",
    name="admin_delete_lender"
)
def delete_lender(
    company_name: str,
    db: Session = Depends(get_db),
    superadmin=Depends(super_admin_required),
):

    try:

        lender = db.query(Lender).join(
            User,
            User.id == Lender.user_id
        ).filter(
            func.lower(Lender.company_name)
            == company_name.lower(),
            User.role == "LENDER"
        ).first()

        if not lender:

            raise HTTPException(
                status_code=404,
                detail="Lender not found"
            )

        user = db.query(User).filter(
            User.id == lender.user_id
        ).first()

        db.delete(lender)

        if user:
            db.delete(user)

        db.commit()

        return {

            "message": (
                "Lender deleted successfully"
            ),

            "id": lender.id,

            "company_name": (
                lender.company_name
            ),
        }

    except HTTPException:
        raise

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )