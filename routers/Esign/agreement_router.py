from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os

from core.database import get_db
from core.dependencies import require_roles
from core.logger import logger

from models.Auth.user import User

from services.Esign.agreement_service import AgreementService
from services.Esign.pdf_generator import PDFGenerator

from schemas.Esign.agreement_schema import AgreementResponse


router = APIRouter(
    prefix="/loan/agreement",
    tags=["Agreement"]
)


# =====================================================
# DEPENDENCY
# =====================================================
def get_agreement_service() -> AgreementService:
    return AgreementService(pdf=PDFGenerator())


# =====================================================
# GENERATE / FETCH AGREEMENT
# =====================================================
@router.post("", response_model=AgreementResponse, operation_id="generate_agreement")
def generate_agreement(
    db: Session = Depends(get_db),
    service: AgreementService = Depends(get_agreement_service),
    current_user: User = Depends(require_roles("USER"))
):
    try:
        logger.info(f"[AGREEMENT GENERATE] user={current_user.id}")

        result = service.fetch_agreement_for_user(
            user_id=current_user.id,
            db=db
        )

        if not result:
            raise HTTPException(404, "Agreement not found")

        return result

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"[AGREEMENT ERROR] user={current_user.id}, error={str(e)}")

        raise HTTPException(
            status_code=500,
            detail="Agreement generation failed"
        )

# =====================================================
# DOWNLOAD AGREEMENT
# =====================================================
@router.get(
    "/download",
    operation_id="download_agreement"
)
def download_agreement(

    db: Session = Depends(get_db),

    service: AgreementService = Depends(
        get_agreement_service
    ),

    current_user: User = Depends(
        require_roles("USER")
    )
):

    try:

        logger.info(
            f"[AGREEMENT DOWNLOAD] "
            f"user={current_user.id}"
        )

        agreement = (
            service.get_existing_agreement(
                user_id=current_user.id,
                db=db
            )
        )

        if not agreement:

            raise HTTPException(
                status_code=404,
                detail=(
                    "Agreement not generated yet"
                )
            )

        # =============================================
        # SERVICE RETURNS DICTIONARY
        # =============================================
        if isinstance(agreement, dict):

            # -----------------------------------------
            # ESIGN NOT COMPLETED
            # -----------------------------------------
            if (
                agreement.get("status")
                != "SIGNED"
            ):

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Please complete e-sign "
                        "before downloading "
                        "agreement"
                    )
                )

            file_path = (
                agreement.get(
                    "signed_pdf_path"
                )
            )

            app_id = (
                agreement.get(
                    "loan_id"
                )
            )

        # =============================================
        # FALLBACK ORM OBJECT
        # =============================================
        else:

            if (
                agreement.esign_status
                != "SIGNED"
            ):

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Please complete e-sign "
                        "before downloading "
                        "agreement"
                    )
                )

            file_path = (
                agreement.signed_pdf_path
            )

            app_id = (
                agreement.application_id
            )

        # =============================================
        # FILE VALIDATION
        # =============================================
        if not file_path:

            raise HTTPException(
                status_code=404,
                detail=(
                    "Signed agreement "
                    "not found"
                )
            )

        # =============================================
        # SECURE PATH VALIDATION
        # =============================================
        base_dir = os.path.abspath(
            "storage"
        )

        abs_path = os.path.abspath(
            file_path
        )

        if not abs_path.startswith(
            base_dir
        ):

            logger.warning(
                f"[SECURITY ALERT] "
                f"path traversal "
                f"user={current_user.id}"
            )

            raise HTTPException(
                status_code=403,
                detail="Invalid file path"
            )

        # =============================================
        # FILE EXISTS
        # =============================================
        if not os.path.exists(
            abs_path
        ):

            raise HTTPException(
                status_code=404,
                detail=(
                    "Signed agreement file "
                    "missing on server"
                )
            )

        logger.info(
            f"[FILE SERVED] "
            f"user={current_user.id}, "
            f"file={abs_path}"
        )

        return FileResponse(

            path=abs_path,

            media_type="application/pdf",

            filename=(
                f"signed_agreement_"
                f"{app_id}.pdf"
            )
        )

    except HTTPException:
        raise

    except Exception as e:

        logger.error(
            f"[DOWNLOAD ERROR] "
            f"user={current_user.id}, "
            f"error={str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to download agreement"
            )
        )


# =====================================================
# VERIFY HASH (ADMIN ONLY)
# =====================================================
@router.post("/verify-hash", operation_id="verify_agreement_hash")
def verify_hash(
    file_hash: str,
    db: Session = Depends(get_db),
    service: AgreementService = Depends(get_agreement_service),
    current_user: User = Depends(require_roles("ADMIN", "SUPER_ADMIN"))
):
    try:
        logger.info(f"[HASH VERIFY] admin={current_user.id}, hash={file_hash}")

        result = service.verify_hash(
            file_hash=file_hash,
            db=db
        )

        if not result:
            raise HTTPException(404, "Hash not found")

        return result

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"[HASH VERIFY ERROR] admin={current_user.id}, error={str(e)}")

        raise HTTPException(
            status_code=500,
            detail="Hash verification failed"
        )