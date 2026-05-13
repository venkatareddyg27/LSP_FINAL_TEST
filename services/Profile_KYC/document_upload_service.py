import os
import re
import socket

from datetime import datetime, timezone

import cloudinary
import cloudinary.uploader

from fastapi import (
    UploadFile,
    HTTPException
)

from sqlalchemy.orm import Session

from core.cloudinary_config import (
    generate_cloudinary_public_id
)

from core.enums import (
    DocumentType,
    DocumentStatus
)

from core.logger import logger

from services.Profile_KYC.kyc_ocr_service import (
    KYCService
)

from repositories.Profile_KYC.user_repository import (
    UserRepository
)

from repositories.Profile_KYC.document_upload_repository import (
    DocumentUploadRepository
)

# =========================================================
# SOCKET TIMEOUT
# =========================================================
socket.setdefaulttimeout(180)

# =========================================================
# FILE LIMITS
# =========================================================
IMAGE_MAX_MB = 5
DOCUMENT_MAX_MB = 10

IMAGE_MAX_BYTES = (
    IMAGE_MAX_MB * 1024 * 1024
)

INCOME_MAX_BYTES = (
    DOCUMENT_MAX_MB * 1024 * 1024
)

# =========================================================
# FILE EXTENSIONS
# =========================================================
ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".pdf"
}

ALLOWED_DOCUMENT_EXTENSIONS = {
    ".pdf"
}

# =========================================================
# MIME TYPES
# =========================================================
ALLOWED_MIME_TYPES = {

    DocumentType.PAN_CARD: {
        "image/jpeg",
        "image/png",
        "application/pdf"
    },

    DocumentType.AADHAAR_FRONT: {
        "image/jpeg",
        "image/png",
        "application/pdf"
    },

    DocumentType.AADHAAR_BACK: {
        "image/jpeg",
        "image/png",
        "application/pdf"
    },

    DocumentType.SALARY_SLIP: {
        "application/pdf"
    },

    DocumentType.BANK_STATEMENT: {
        "application/pdf"
    },
}

# =========================================================
# OCR SCORE THRESHOLDS
# =========================================================
SCORE_APPROVE = 90
SCORE_UNDER_REVIEW = 70


class DocumentUploadService:

    # =====================================================
    # INCOME DOC TYPES
    # =====================================================
    INCOME_PROOF_DOCS = {

        DocumentType.SALARY_SLIP,

        DocumentType.BANK_STATEMENT
    }

    # =====================================================
    # VALIDATE FILE
    # =====================================================
    @staticmethod
    def _validate_file(
        file: UploadFile,
        doc_type: DocumentType,
        file_size: int
    ) -> None:

        if file_size <= 0:

            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty"
            )

        max_bytes = (

            INCOME_MAX_BYTES

            if doc_type in (
                DocumentUploadService
                .INCOME_PROOF_DOCS
            )

            else IMAGE_MAX_BYTES
        )

        if file_size > max_bytes:

            max_mb = (
                max_bytes / (1024 * 1024)
            )

            actual_mb = round(
                file_size / (1024 * 1024),
                2
            )

            raise HTTPException(
                status_code=400,
                detail={
                    "error": "File too large",

                    "document_type": (
                        doc_type.value
                    ),

                    "file_size_mb": (
                        actual_mb
                    ),

                    "max_allowed_mb": (
                        max_mb
                    ),

                    "message": (
                        f"{doc_type.value}: "
                        f"{actual_mb} MB exceeds "
                        f"{max_mb} MB limit."
                    ),
                }
            )

        ext = os.path.splitext(
            file.filename
        )[1].lower()

        if doc_type in [

            DocumentType.PAN_CARD,

            DocumentType.AADHAAR_FRONT,

            DocumentType.AADHAAR_BACK
        ]:

            if ext not in ALLOWED_IMAGE_EXTENSIONS:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"{doc_type.value} "
                        f"requires JPG, PNG "
                        f"or PDF. Got: {ext}."
                    ),
                )

        elif (
            doc_type
            in DocumentUploadService
            .INCOME_PROOF_DOCS
        ):

            if (
                ext
                not in ALLOWED_DOCUMENT_EXTENSIONS
            ):

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"{doc_type.value} "
                        f"requires PDF. "
                        f"Got: {ext}."
                    ),
                )

        allowed_mimes = (
            ALLOWED_MIME_TYPES
            .get(doc_type, set())
        )

        if (
            file.content_type
            not in allowed_mimes
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid MIME type "
                    f"for {doc_type.value}: "
                    f"{file.content_type}"
                )
            )

    # =====================================================
    # OCR
    # =====================================================
    @staticmethod
    def _run_ocr(
        temp_path: str
    ) -> str:

        raw_text = (
            KYCService.extract_text(
                temp_path
            )
        )

        if raw_text and len(raw_text) > 50000:

            raw_text = raw_text[:50000]

        return raw_text

    # =====================================================
    # OCR VALIDATION
    # =====================================================
    @staticmethod
    def _validate_ocr(
        doc_type: DocumentType,
        raw_text: str,
        user
    ):

        if doc_type == DocumentType.PAN_CARD:

            return (
                KYCService.process_pan(
                    raw_text,
                    user
                )
            )

        elif doc_type in [

            DocumentType.AADHAAR_FRONT,

            DocumentType.AADHAAR_BACK
        ]:

            return (
                KYCService.process_aadhaar(
                    raw_text,
                    user
                )
            )

        return {

            "comparison": {
                "verified": True
            },

            "failed_reasons": []
        }

    # =====================================================
    # CALCULATE SCORE
    # =====================================================
    @staticmethod
    def _calculate_score(
        validation_result: dict
    ) -> int:

        comparison = (
            validation_result
            .get("comparison", {})
        )

        verified = comparison.get(
            "verified",
            False
        )

        if verified:
            return 100

        failed_count = len(
            validation_result.get(
                "failed_reasons",
                []
            )
        )

        if failed_count == 1:
            return 75

        return 40

    # =====================================================
    # DECIDE STATUS
    # =====================================================
    @staticmethod
    def _decide_status(
        score: int
    ):

        if score >= SCORE_APPROVE:

            return (
                DocumentStatus.APPROVED
            )

        if (
            score >= SCORE_UNDER_REVIEW
            and score < SCORE_APPROVE
        ):

            return (
                DocumentStatus.UNDER_REVIEW
            )

        return (
            DocumentStatus.REJECTED
        )

    # =====================================================
    # CLOUDINARY UPLOAD
    # =====================================================
    @staticmethod
    def _upload_to_cloudinary(
        temp_path: str,
        folder: str,
        public_id: str
    ):

        try:

            result = (
                cloudinary.uploader.upload(

                    temp_path,

                    folder=folder,

                    public_id=public_id,

                    resource_type="auto",

                    overwrite=True,

                    use_filename=False,

                    unique_filename=False,

                    timeout=180,
                )
            )

            return {

                "url": result.get(
                    "secure_url"
                ),

                "public_id": result.get(
                    "public_id"
                )
            }

        except Exception as e:

            logger.exception(
                "[CLOUDINARY ERROR]"
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    f"Cloudinary upload failed: "
                    f"{str(e)}"
                )
            )

    # =====================================================
    # DELETE DOCUMENT
    # =====================================================
    @staticmethod
    def delete_document(
        db: Session,
        user_id: int,
        document_id: int
    ):

        try:

            document = (
                DocumentUploadRepository
                .get_by_id(
                    db=db,
                    document_id=document_id
                )
            )

            if not document:

                raise HTTPException(
                    status_code=404,
                    detail="Document not found"
                )

            if document.user_id != user_id:

                raise HTTPException(
                    status_code=403,
                    detail="Unauthorized access"
                )

            # =============================================
            # DELETE FROM CLOUDINARY
            # =============================================
            try:

                extracted_data = (
                    document.extracted_data
                    or {}
                )

                cloudinary_public_id = (
                    extracted_data.get(
                        "cloudinary_public_id"
                    )
                )

                if cloudinary_public_id:

                    # =====================================
                    # DETECT RESOURCE TYPE
                    # =====================================
                    resource_type = "image"

                    if document.file_name:

                        lower_name = (
                            document.file_name.lower()
                        )

                        if lower_name.endswith(".pdf"):

                            resource_type = "raw"

                    # =====================================
                    # DELETE FILE
                    # =====================================
                    cloudinary.uploader.destroy(
                        cloudinary_public_id,
                        resource_type=resource_type
                    )

                    logger.info(
                        f"[CLOUDINARY DELETE] "
                        f"public_id="
                        f"{cloudinary_public_id}, "
                        f"resource_type="
                        f"{resource_type}"
                    )

            except Exception as cloudinary_error:

                logger.exception(
                    "[CLOUDINARY DELETE ERROR]"
                )

                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"Cloudinary delete failed: "
                        f"{str(cloudinary_error)}"
                    )
                )
            # =============================================
            # DELETE DB RECORD
            # =============================================
            DocumentUploadRepository.delete_document(
                db=db,
                document=document
            )

            logger.info(
                f"[DOCUMENT DELETED] "
                f"user={user_id}, "
                f"document_id={document_id}"
            )

            return {

                "success": True,

                "document_id": document_id,

                "message": (
                    "Document deleted successfully"
                )
            }

        except HTTPException:
            raise

        except Exception as e:

            logger.exception(
                "[DELETE DOCUMENT ERROR]"
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    f"Failed to delete document: "
                    f"{str(e)}"
                )
            )

    # =====================================================
    # PROCESS DOCUMENT
    # =====================================================
    @staticmethod
    def process_document(
        db: Session,
        user_id: int,
        file: UploadFile,
        doc_type: DocumentType
    ):

        user = (
            UserRepository
            .get_by_user_id(
                db,
                user_id
            )
        )

        if not user:

            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        file.file.seek(0)

        content = file.file.read()

        file_size = len(content)

        (
            DocumentUploadService
            ._validate_file(
                file,
                doc_type,
                file_size
            )
        )

        safe_filename = re.sub(
            r'[^A-Za-z0-9._-]',
            '_',
            file.filename
        )

        ext = os.path.splitext(
            safe_filename
        )[1]

        temp_path = (
            f"temp_{datetime.utcnow().timestamp()}"
            f"{ext}"
        )

        try:

            with open(
                temp_path,
                "wb"
            ) as f:

                f.write(content)

            # =============================================
            # SKIP OCR FOR INCOME DOCS
            # =============================================
            if doc_type in [

                DocumentType.SALARY_SLIP,

                DocumentType.BANK_STATEMENT
            ]:

                raw_text = ""

                validation_result = {

                    "comparison": {
                        "verified": True
                    },

                    "failed_reasons": []
                }

            else:

                raw_text = (
                    DocumentUploadService
                    ._run_ocr(temp_path)
                )

                validation_result = (
                    DocumentUploadService
                    ._validate_ocr(
                        doc_type,
                        raw_text,
                        user
                    )
                )

            score = (
                DocumentUploadService
                ._calculate_score(
                    validation_result
                )
            )

            status = (
                DocumentUploadService
                ._decide_status(
                    score
                )
            )

            public_id = (
                generate_cloudinary_public_id(
                    user_id,
                    doc_type.value
                )
            )

            upload_result = (
                DocumentUploadService
                ._upload_to_cloudinary(

                    temp_path=temp_path,

                    folder=(
                        f"loan_kyc/"
                        f"{user_id}"
                    ),

                    public_id=public_id
                )
            )

            document = (
                DocumentUploadRepository
                .create_or_replace_document(
                    db=db,

                    user_id=user_id,

                    document_type=doc_type,

                    file_name=safe_filename,

                    file_url=(
                        upload_result["url"]
                    ),

                    cloudinary_public_id=(
                        upload_result[
                            "public_id"
                        ]
                    ),

                    status=status,

                    verification_score=score,

                    ocr_text=(
                        raw_text[:10000]
                        if raw_text
                        else None
                    ),

                    rejection_reason=(
                        ", ".join(
                            validation_result
                            .get(
                                "failed_reasons",
                                []
                            )
                        )
                    ),

                    uploaded_at=(
                        datetime.now(
                            timezone.utc
                        )
                    ),
                )
            )

            return {

                "document_id": (
                    document.id
                ),

                "document_type": (
                    doc_type.value
                ),

                "status": (
                    status.value
                ),

                "score": score,

                "file_url": (
                    document.file_path
                ),

                "validation": (
                    validation_result
                ),

                "message": (
                    "Document uploaded successfully"
                )
            }

        finally:

            if os.path.exists(
                temp_path
            ):

                os.remove(temp_path)

    # =====================================================
    # BULK DOCUMENT UPLOAD
    # =====================================================
    @staticmethod
    def bulk_upload_documents(
        db: Session,
        user_id: int,

        pan_card: UploadFile = None,

        aadhaar_front: UploadFile = None,

        aadhaar_back: UploadFile = None,

        income_proof: UploadFile = None,

        salary_slip: UploadFile = None,

        bank_statement: UploadFile = None,

        income_type: str = None,
    ):

        uploaded_documents = []

        failed_documents = []

        files = {

            DocumentType.PAN_CARD: (
                pan_card
            ),

            DocumentType.AADHAAR_FRONT: (
                aadhaar_front
            ),

            DocumentType.AADHAAR_BACK: (
                aadhaar_back
            ),
        }

        # =============================================
        # INCOME PROOF
        # =============================================
        if income_proof and income_type:

            if income_type == "SALARY_SLIP":

                files[
                    DocumentType.SALARY_SLIP
                ] = income_proof

            elif income_type == "BANK_STATEMENT":

                files[
                    DocumentType.BANK_STATEMENT
                ] = income_proof

        if salary_slip:

            files[
                DocumentType.SALARY_SLIP
            ] = salary_slip

        if bank_statement:

            files[
                DocumentType.BANK_STATEMENT
            ] = bank_statement

        # =============================================
        # PROCESS FILES
        # =============================================
        for doc_type, file in files.items():

            if not file:
                continue

            try:

                result = (
                    DocumentUploadService
                    .process_document(
                        db=db,
                        user_id=user_id,
                        file=file,
                        doc_type=doc_type
                    )
                )

                uploaded_documents.append({

                    "document_type": (
                        doc_type.value
                    ),

                    "status": "SUCCESS",

                    "data": result
                })

            except Exception as e:

                failed_documents.append({

                    "document_type": (
                        doc_type.value
                    ),

                    "status": "FAILED",

                    "error": str(e)
                })

        if (
            not uploaded_documents
            and not failed_documents
        ):

            raise HTTPException(
                status_code=400,
                detail="No documents uploaded"
            )

        return {

            "uploaded_documents": (
                uploaded_documents
            ),

            "failed_documents": (
                failed_documents
            ),

            "total_uploaded": (
                len(uploaded_documents)
            ),

            "total_failed": (
                len(failed_documents)
            ),

            "message": (
                "Documents upload completed"
            )
        }

    # =====================================================
    # LIST DOCUMENTS
    # =====================================================
    @staticmethod
    def list_documents(
        db: Session,
        user_id: int
    ):

        user = (
            UserRepository
            .get_by_user_id(
                db,
                user_id
            )
        )

        if not user:

            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        documents = (
            DocumentUploadRepository
            .get_user_documents(
                db=db,
                user_id=user_id
            )
        )

        response_documents = []

        uploaded_doc_types = []

        for doc in documents:

            doc_type = (

                doc.document_type.value

                if hasattr(
                    doc.document_type,
                    "value"
                )

                else str(
                    doc.document_type
                )
            )

            if (
                str(doc.status)
                != "REJECTED"
            ):

                if (
                    doc_type
                    not in uploaded_doc_types
                ):

                    uploaded_doc_types.append(
                        doc_type
                    )

            response_documents.append({

                "id": (
                    doc.id
                ),

                "document_type": (
                    doc_type
                ),

                "file_name": (
                    doc.file_name
                ),

                "file_url": (
                    doc.file_path
                ),

                "status": (

                    doc.status.value

                    if hasattr(
                        doc.status,
                        "value"
                    )

                    else str(
                        doc.status
                    )
                ),

                "uploaded_at": (
                    doc.uploaded_at
                ),
            })

        required_documents = [

            DocumentType.PAN_CARD.value,

            DocumentType.AADHAAR_FRONT.value,

            DocumentType.AADHAAR_BACK.value,
        ]

        income_type = getattr(
            user,
            "income_type",
            None
        )

        if hasattr(
            income_type,
            "value"
        ):

            income_type = (
                income_type.value
            )

        if income_type:

            income_type = (
                str(income_type)
                .strip()
                .upper()
            )

        if income_type == "SALARY_SLIP":

            required_documents.append(
                DocumentType.SALARY_SLIP.value
            )

        elif income_type == "BANK_STATEMENT":

            required_documents.append(
                DocumentType.BANK_STATEMENT.value
            )

        missing_documents = [

            doc

            for doc in required_documents

            if doc not in uploaded_doc_types
        ]

        return {

            "user_id": (
                user_id
            ),

            "email": (
                user.email
            ),

            "documents": (
                response_documents
            ),

            "total_documents": (
                len(response_documents)
            ),

            "required_documents": (
                required_documents
            ),

            "missing_documents": (
                missing_documents
            ),

            "all_approved": (
                len(missing_documents) == 0
            )
        }