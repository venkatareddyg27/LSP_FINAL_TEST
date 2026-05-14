from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models.Profile_KYC.document_upload import (
    DocumentUpload,
    DocumentType,
    DocumentStatus,
)


class DocumentUploadRepository:

    # =========================================================================
    # CREATE OR REPLACE DOCUMENT
    # Always replaces the existing record for this user + doc_type
    # so there is only ever one row per document type per user.
    # =========================================================================
    @staticmethod
    def create_or_replace_document(
        db: Session,
        user_id: int,
        email: str,
        document_type: DocumentType,
        file_name: str,
        file_path: str,
        file_size: int,
        mime_type: str,
        cloudinary_public_id: str,
        status: DocumentStatus,
        match_score: float,
        ocr_text: str | None,
        admin_remarks: str | None,
        uploaded_at: datetime,
    ) -> DocumentUpload:

        existing = (
            db.query(DocumentUpload)
            .filter(
                DocumentUpload.user_id == user_id,
                DocumentUpload.document_type == document_type,
            )
            .first()
        )

        if existing:

            existing.email = email
            existing.file_name = file_name
            existing.file_path = file_path
            existing.file_size = file_size
            existing.mime_type = mime_type
            existing.status = status
            existing.match_score = match_score
            existing.ocr_text = ocr_text
            existing.admin_remarks = admin_remarks
            existing.uploaded_at = uploaded_at

            # Reset review fields on re-upload
            existing.reviewed_at = None
            existing.reviewed_by = None
            existing.ocr_verified = None

            existing.extracted_data = {
                "cloudinary_public_id": cloudinary_public_id
            }

            db.commit()

            db.refresh(existing)

            return existing

        document = DocumentUpload(

            user_id=user_id,

            email=email,

            document_type=document_type,

            file_name=file_name,

            file_path=file_path,

            file_size=file_size,

            mime_type=mime_type,

            status=status,

            match_score=match_score,

            ocr_text=ocr_text,

            admin_remarks=admin_remarks,

            uploaded_at=uploaded_at,

            reviewed_at=None,

            reviewed_by=None,

            ocr_verified=None,

            extracted_data={
                "cloudinary_public_id": cloudinary_public_id
            },
        )

        db.add(document)

        db.commit()

        db.refresh(document)

        return document

    # =========================================================================
    # GET BY ID
    # =========================================================================
    @staticmethod
    def get_by_id(
        db: Session,
        document_id: int,
    ) -> DocumentUpload | None:

        return (
            db.query(DocumentUpload)
            .filter(
                DocumentUpload.id == document_id
            )
            .first()
        )

    # =========================================================================
    # GET LATEST BY TYPE
    # =========================================================================
    @staticmethod
    def get_latest_by_type(
        db: Session,
        user_id: int,
        document_type: DocumentType,
    ) -> DocumentUpload | None:

        return (
            db.query(DocumentUpload)
            .filter(
                DocumentUpload.user_id == user_id,
                DocumentUpload.document_type == document_type,
            )
            .order_by(
                DocumentUpload.uploaded_at.desc()
            )
            .first()
        )

    # =========================================================================
    # GET USER DOCUMENTS
    # =========================================================================
    @staticmethod
    def get_user_documents(
        db: Session,
        user_id: int,
    ) -> list[DocumentUpload]:

        return (
            db.query(DocumentUpload)
            .filter(
                DocumentUpload.user_id == user_id
            )
            .order_by(
                DocumentUpload.uploaded_at.desc()
            )
            .all()
        )

    # =========================================================================
    # GET DOCUMENTS FOR ADMIN REVIEW
    # =========================================================================
    @staticmethod
    def get_documents_for_admin_review(
        db: Session,
        status_filter: str = "UNDER_REVIEW",
        skip: int = 0,
        limit: int = 50,
    ) -> list[DocumentUpload]:

        return (
            db.query(DocumentUpload)
            .filter(
                DocumentUpload.status == status_filter
            )
            .order_by(
                DocumentUpload.uploaded_at.desc()
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    # =========================================================================
    # GET UNDER REVIEW DOCUMENTS
    # =========================================================================
    @staticmethod
    def get_under_review_documents(
        db: Session,
        user_id: int | None = None,
    ) -> list[DocumentUpload]:

        query = (
            db.query(DocumentUpload)
            .filter(
                DocumentUpload.status
                == DocumentStatus.UNDER_REVIEW
            )
        )

        if user_id:

            query = query.filter(
                DocumentUpload.user_id == user_id
            )

        return (
            query
            .order_by(
                DocumentUpload.uploaded_at.desc()
            )
            .all()
        )

    # =========================================================================
    # GET USER UNDER REVIEW DOCUMENTS
    # =========================================================================
    @staticmethod
    def get_user_under_review_documents(
        db: Session,
        user_id: int,
    ) -> list[DocumentUpload]:

        return (
            db.query(DocumentUpload)
            .filter(
                DocumentUpload.user_id == user_id,
                DocumentUpload.status
                == DocumentStatus.UNDER_REVIEW
            )
            .order_by(
                DocumentUpload.uploaded_at.desc()
            )
            .all()
        )

    # =========================================================================
    # COUNT ALL DOCUMENTS
    # =========================================================================
    @staticmethod
    def count_all(
        db: Session
    ) -> int:

        return (
            db.query(DocumentUpload)
            .count()
        )

    # =========================================================================
    # COUNT DOCUMENTS BY STATUS
    # =========================================================================
    @staticmethod
    def count_by_status(
        db: Session,
        status: DocumentStatus
    ) -> int:

        return (
            db.query(DocumentUpload)
            .filter(
                DocumentUpload.status == status
            )
            .count()
        )

    # =========================================================================
    # UPDATE DOCUMENT
    # =========================================================================
    @staticmethod
    def update_document(
        db: Session,
        document: DocumentUpload,
    ) -> DocumentUpload:

        db.commit()

        db.refresh(document)

        return document

    # =========================================================================
    # GET DOCUMENTS BY USER ID
    # =========================================================================
    @staticmethod
    def get_by_user_id(
        db: Session,
        user_id: int,
    ) -> list[DocumentUpload]:

        return (
            db.query(DocumentUpload)
            .filter(
                DocumentUpload.user_id == user_id
            )
            .order_by(
                DocumentUpload.uploaded_at.desc()
            )
            .all()
        )

    # =========================================================================
    # ADMIN UPDATE DOCUMENT
    # Approve or reject document
    # =========================================================================
    @staticmethod
    def admin_update_document(
        db: Session,
        document_id: int,
        new_status: str,
        admin_remarks: str | None,
        reviewed_by: str | None = None,
    ) -> DocumentUpload | None:

        doc = (
            db.query(DocumentUpload)
            .filter(
                DocumentUpload.id == document_id
            )
            .first()
        )

        if not doc:
            return None

        doc.status = new_status

        doc.admin_remarks = admin_remarks

        doc.reviewed_at = datetime.now(
            timezone.utc
        )

        doc.reviewed_by = reviewed_by

        db.commit()

        db.refresh(doc)

        return doc

    # =========================================================================
    # DELETE DOCUMENT
    # =========================================================================
    @staticmethod
    def delete_document(
        db: Session,
        document: DocumentUpload,
    ) -> None:

        db.delete(document)

        db.commit()