from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from models.Profile_KYC.document_upload import (
    DocumentUpload,
    DocumentType,
    DocumentStatus
)

from repositories.Profile_KYC.user_repository import (
    UserRepository
)


class DocumentUploadRepository:

    # =====================================================
    # GET BY ID
    # =====================================================
    @staticmethod
    def get_by_id(
        db: Session,
        document_id: int
    ) -> Optional[DocumentUpload]:

        return (
            db.query(DocumentUpload)
            .filter(
                DocumentUpload.id
                == document_id
            )
            .first()
        )

    # =====================================================
    # GET BY USER
    # =====================================================
    @staticmethod
    def get_by_user_id(
        db: Session,
        user_id: int
    ) -> List[DocumentUpload]:

        return (
            db.query(DocumentUpload)
            .filter(
                DocumentUpload.user_id
                == user_id
            )
            .all()
        )

    # =====================================================
    # GET USER DOCUMENTS
    # =====================================================
    @staticmethod
    def get_user_documents(
        db: Session,
        user_id: int
    ) -> List[DocumentUpload]:

        return (

            db.query(
                DocumentUpload
            )

            .filter(
                DocumentUpload.user_id
                == user_id
            )

            .all()
        )

    # =====================================================
    # GET BY EMAIL
    # =====================================================
    @staticmethod
    def get_by_email(
        db: Session,
        email: str
    ) -> List[DocumentUpload]:

        return (
            db.query(DocumentUpload)
            .filter(
                DocumentUpload.email
                == email
            )
            .all()
        )

    # =====================================================
    # GET USER DOCUMENT
    # =====================================================
    @staticmethod
    def get_by_user_and_type(
        db: Session,
        user_id: int,
        document_type: DocumentType
    ) -> Optional[DocumentUpload]:

        return (
            db.query(DocumentUpload)
            .filter(
                DocumentUpload.user_id
                == user_id,

                DocumentUpload.document_type
                == document_type,
            )
            .first()
        )

    # =====================================================
    # CREATE DOCUMENT
    # =====================================================
    @staticmethod
    def create_document(
        db: Session,
        document: DocumentUpload
    ) -> DocumentUpload:

        db.add(document)

        db.commit()

        db.refresh(document)

        return document

    # =====================================================
    # UPDATE DOCUMENT
    # =====================================================
    @staticmethod
    def update_document(
        db: Session,
        document: DocumentUpload
    ) -> DocumentUpload:

        db.commit()

        db.refresh(document)

        return document

    # =====================================================
    # DELETE DOCUMENT
    # =====================================================
    @staticmethod
    def delete_document(
        db: Session,
        document: DocumentUpload
    ) -> None:

        db.delete(document)

        db.commit()

    # =====================================================
    # COUNT ALL
    # =====================================================
    @staticmethod
    def count_all(
        db: Session
    ) -> int:

        return (
            db.query(DocumentUpload)
            .count()
        )

    # =====================================================
    # COUNT BY STATUS
    # =====================================================
    @staticmethod
    def count_by_status(
        db: Session,
        status: DocumentStatus
    ) -> int:

        return (
            db.query(DocumentUpload)
            .filter(
                DocumentUpload.status
                == status
            )
            .count()
        )

    # =====================================================
    # GET PENDING
    # =====================================================
    @staticmethod
    def get_pending_documents(
        db: Session
    ) -> List[DocumentUpload]:

        return (
            db.query(DocumentUpload)
            .filter(
                DocumentUpload.status
                == DocumentStatus.UNDER_REVIEW
            )
            .all()
        )

    # =====================================================
    # GET REJECTED
    # =====================================================
    @staticmethod
    def get_rejected_documents_before_date(
        db: Session,
        cutoff_date: datetime
    ) -> List[DocumentUpload]:

        return (
            db.query(DocumentUpload)
            .filter(
                DocumentUpload.status
                == DocumentStatus.REJECTED,

                DocumentUpload.reviewed_at
                < cutoff_date,
            )
            .all()
        )

    # =====================================================
    # GET BY USER + STATUS
    # =====================================================
    @staticmethod
    def get_by_user_and_status(
        db: Session,
        user_id: int,
        status: DocumentStatus
    ) -> List[DocumentUpload]:

        return (
            db.query(DocumentUpload)
            .filter(
                DocumentUpload.user_id
                == user_id,

                DocumentUpload.status
                == status,
            )
            .all()
        )

    # =====================================================
    # CREATE OR REPLACE DOCUMENT
    # =====================================================
    @staticmethod
    def create_or_replace_document(
        db: Session,
        user_id: int,
        document_type: DocumentType,
        file_name: str,
        file_url: str,
        cloudinary_public_id: str,
        status: DocumentStatus,
        verification_score: int,
        ocr_text: str = None,
        rejection_reason: str = None,
        uploaded_at=None,
    ):

        # =================================================
        # USER
        # =================================================
        user = (
            UserRepository
            .get_by_user_id(
                db,
                user_id
            )
        )

        # =================================================
        # EXISTING DOCUMENT
        # =================================================
        document = (
            DocumentUploadRepository
            .get_by_user_and_type(
                db,
                user_id,
                document_type
            )
        )

        # =================================================
        # OCR DATA
        # =================================================
        extracted_data = {

            "cloudinary_public_id": (
                cloudinary_public_id
            ),

            "rejection_reason": (
                rejection_reason
            )
        }

        ocr_verified = (
            1
            if verification_score >= 90
            else 0
        )

        # =================================================
        # UPDATE EXISTING
        # =================================================
        if document:

            document.email = (
                user.email
            )

            document.file_name = (
                file_name
            )

            document.file_path = (
                file_url
            )

            document.file_size = 0

            document.mime_type = (
                "application/octet-stream"
            )

            document.status = (
                status
            )

            document.ocr_text = (
                ocr_text
            )

            document.extracted_data = (
                extracted_data
            )

            document.match_score = (
                verification_score
            )

            document.ocr_verified = (
                ocr_verified
            )

            document.uploaded_at = (
                uploaded_at
            )

        # =================================================
        # CREATE NEW
        # =================================================
        else:

            document = DocumentUpload(

                user_id=user_id,

                email=user.email,

                document_type=document_type,

                file_name=file_name,

                file_path=file_url,

                file_size=0,

                mime_type=(
                    "application/octet-stream"
                ),

                status=status,

                ocr_text=ocr_text,

                extracted_data=(
                    extracted_data
                ),

                match_score=(
                    verification_score
                ),

                ocr_verified=(
                    ocr_verified
                ),

                uploaded_at=uploaded_at,
            )

            db.add(document)

        # =================================================
        # SAVE
        # =================================================
        db.commit()

        db.refresh(document)

        return document