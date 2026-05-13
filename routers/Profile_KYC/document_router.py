from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form
)

from typing import Optional

from sqlalchemy.orm import Session

from core.database import get_db

from core.dependencies import require_roles

from models.Auth.user import User

from schemas.Profile_KYC.document_schema import (
    AllDocumentsResponse,
    DocumentListItem,
    IncomeTypeEnum,
)

from services.Profile_KYC.document_upload_service import (
    DocumentUploadService
)

router = APIRouter(
    prefix="/kyc/documents",
    tags=["Document Upload"]
)


# =====================================================
# POST /upload
# =====================================================
@router.post("/upload")
async def upload_documents(

    pan_card: Optional[UploadFile] = File(
        None,
        description=(
            "PAN Card — JPG/PNG/PDF"
        )
    ),

    aadhaar_front: Optional[UploadFile] = File(
        None,
        description=(
            "Aadhaar Front — JPG/PNG/PDF"
        )
    ),

    aadhaar_back: Optional[UploadFile] = File(
        None,
        description=(
            "Aadhaar Back — JPG/PNG/PDF"
        )
    ),

    income_proof: Optional[UploadFile] = File(
        None,
        description=(
            "Salary Slip or "
            "Bank Statement — PDF"
        )
    ),

    income_type: Optional[IncomeTypeEnum] = Form(
        None,
        description=(
            "SALARY_SLIP or "
            "BANK_STATEMENT"
        )
    ),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_roles("USER")
    ),
):

    # =================================================
    # PROFILE
    # =================================================
    profile = current_user.profile

    if not profile:

        raise HTTPException(
            status_code=404,
            detail="KYC profile not found"
        )

    # =================================================
    # CHECK FILES
    # =================================================
    files_provided = [

        f for f in [

            pan_card,

            aadhaar_front,

            aadhaar_back,

            income_proof

        ]

        if f and f.filename
    ]

    if not files_provided:

        raise HTTPException(
            status_code=400,
            detail=(
                "No files provided. "
                "Please upload at least "
                "one document."
            )
        )

    # =================================================
    # FILE SIZE VALIDATION
    # =================================================
    IMAGE_MAX = 5 * 1024 * 1024

    PDF_MAX = 10 * 1024 * 1024

    for field_name, file, label, max_bytes in [

        (
            "pan_card",
            pan_card,
            "PAN Card",
            IMAGE_MAX
        ),

        (
            "aadhaar_front",
            aadhaar_front,
            "Aadhaar Front",
            IMAGE_MAX
        ),

        (
            "aadhaar_back",
            aadhaar_back,
            "Aadhaar Back",
            IMAGE_MAX
        ),

        (
            "income_proof",
            income_proof,
            "Income Proof",
            PDF_MAX
        ),
    ]:

        if file and file.filename:

            content = await file.read()

            # RESET POINTER
            file.file.seek(0)

            if len(content) > max_bytes:

                max_mb = (
                    max_bytes / (1024 * 1024)
                )

                actual_mb = round(
                    len(content) / (1024 * 1024),
                    2
                )

                raise HTTPException(
                    status_code=400,
                    detail={

                        "error": (
                            "File too large"
                        ),

                        "field": label,

                        "file_size_mb": (
                            actual_mb
                        ),

                        "max_allowed_mb": (
                            max_mb
                        ),

                        "message": (
                            f"{label}: "
                            f"{actual_mb} MB "
                            f"exceeds the "
                            f"{max_mb} MB limit."
                        ),
                    }
                )

    # =================================================
    # INCOME TYPE VALIDATION
    # =================================================
    if income_proof and not income_type:

        raise HTTPException(
            status_code=400,
            detail=(
                "income_type is required "
                "when income_proof is uploaded"
            )
        )

    # =================================================
    # UPLOAD DOCUMENTS
    # =================================================
    try:

        result = (
            DocumentUploadService
            .bulk_upload_documents(

                db=db,

                user_id=(
                    profile.user_id
                ),

                pan_card=(
                    pan_card
                ),

                aadhaar_front=(
                    aadhaar_front
                ),

                aadhaar_back=(
                    aadhaar_back
                ),

                income_proof=(
                    income_proof
                ),

                income_type=(

                    income_type.value

                    if income_type

                    else None
                ),
            )
        )

        # =================================================
        # SUCCESS DOCUMENTS
        # =================================================
        uploaded = []

        for doc in result.get(
            "uploaded_documents",
            []
        ):

            uploaded.append({

                "document_type": (
                    doc.get(
                        "document_type"
                    )
                ),

                "status": (
                    doc.get("status")
                ),

                "data": (
                    doc.get("data")
                )
            })

        # =================================================
        # FAILED DOCUMENTS
        # =================================================
        failed = []

        for doc in result.get(
            "failed_documents",
            []
        ):

            failed.append({

                "document_type": (
                    doc.get(
                        "document_type"
                    )
                ),

                "status": (
                    doc.get("status")
                ),

                "error": (
                    doc.get("error")
                ),

                "reason": (
                    doc.get(
                        "reason",
                        []
                    )
                ),

                "data": (
                    doc.get("data")
                )
            })

        # =================================================
        # RESPONSE
        # =================================================
        return {

            "user_id": (
                result.get("user_id")
            ),

            "email": (
                result.get("email")
            ),

            "uploaded_documents": (
                uploaded
            ),

            "total_uploaded": (
                result.get(
                    "total_uploaded",
                    0
                )
            ),

            "total_failed": (
                result.get(
                    "total_failed",
                    0
                )
            ),

            "failed_documents": (
                failed
            ),

            "skipped_approved": (
                result.get(
                    "skipped_approved",
                    []
                )
            ),

            "skipped_empty": (
                result.get(
                    "skipped_empty",
                    []
                )
            ),

            "missing_documents": (
                result.get(
                    "missing_documents",
                    []
                )
            ),

            "all_required_uploaded": (
                result.get(
                    "all_required_uploaded",
                    False
                )
            ),

            "document_status": (
                result.get(
                    "document_status"
                )
            ),

            "kyc_status": (
                result.get(
                    "kyc_status"
                )
            ),

            "message": (
                result.get(
                    "message"
                )
            )
        }

    except HTTPException:

        raise

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Document upload "
                f"failed: {str(exc)}"
            )
        )


# =====================================================
# GET /list
# =====================================================
@router.get(
    "/list",
    response_model=AllDocumentsResponse
)
def list_documents(

    db: Session = Depends(
        get_db
    ),

    current_user: User = Depends(
        require_roles("USER")
    ),
):

    profile = current_user.profile

    if not profile:

        raise HTTPException(
            status_code=404,
            detail="KYC profile not found"
        )

    try:

        result = (
            DocumentUploadService
            .list_documents(
                db=db,
                user_id=profile.user_id
            )
        )

        documents = [

            DocumentListItem(
                **doc
            )

            for doc in (
                result["documents"]
            )
        ]

        return (
            AllDocumentsResponse(

                user_id=(
                    result["user_id"]
                ),

                email=(
                    result["email"]
                ),

                documents=(
                    documents
                ),

                total_documents=(
                    result[
                        "total_documents"
                    ]
                ),

                required_documents=(
                    result[
                        "required_documents"
                    ]
                ),

                missing_documents=(
                    result[
                        "missing_documents"
                    ]
                ),

                all_approved=(
                    result[
                        "all_approved"
                    ]
                ),
            )
        )

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=(str(e)
            )
        )


# =====================================================
# DELETE /{document_id}
# =====================================================
@router.delete(
    "/{document_id}"
)
def delete_document(

    document_id: int,

    db: Session = Depends(
        get_db
    ),

    current_user: User = Depends(
        require_roles("USER")
    ),
):

    profile = current_user.profile

    if not profile:

        raise HTTPException(
            status_code=404,
            detail="KYC profile not found"
        )

    try:

        return (
            DocumentUploadService
            .delete_document(

                db=db,

                document_id=(
                    document_id
                ),

                user_id=(
                    profile.user_id
                ),
            )
        )

    except HTTPException:

        raise

    except Exception:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to delete "
                "document"
            )
        )