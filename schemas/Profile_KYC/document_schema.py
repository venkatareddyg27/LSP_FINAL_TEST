from datetime import datetime

from pydantic import BaseModel
from typing import Optional, List
from enum import Enum


class IncomeTypeEnum(str, Enum):
    SALARY_SLIP    = "SALARY_SLIP"
    BANK_STATEMENT = "BANK_STATEMENT"


class DocumentStatusEnum(str, Enum):
    UPLOADED     = "UPLOADED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED     = "APPROVED"
    REJECTED     = "REJECTED"


class ReviewAction(str, Enum):
    APPROVE = "APPROVE"
    REJECT  = "REJECT"


# =========================================================
# SINGLE DOCUMENT
# =========================================================
class SingleDocumentResult(BaseModel):

    document_type:  str

    file_name: Optional[str] = None

    file_size: Optional[int] = None

    status: str

    uploaded_at: Optional[datetime] = None

    match_score: Optional[float] = None

    ocr_verified: Optional[int] = None

    failed_reasons: List[str] = []

    message: Optional[str] = None


# =========================================================
# FAILED DOCUMENT
# =========================================================
class FailedDocumentResult(BaseModel):

    document_type: str

    status: str

    error: Optional[str] = None

    reason: Optional[List[str]] = []


# =========================================================
# BULK UPLOAD RESPONSE
# =========================================================
class BulkDocumentUploadResponse(BaseModel):

    user_id: int

    email: str

    uploaded_documents: List[dict]

    failed_documents: List[FailedDocumentResult]

    total_uploaded: int

    total_failed: int

    skipped_approved: List[str]

    skipped_empty: List[str]

    missing_documents: List[str]

    all_required_uploaded: bool

    document_status: str

    kyc_status: str

    message: str


# =========================================================
# DOCUMENT LIST ITEM
# =========================================================
class DocumentListItem(BaseModel):

    id: int

    document_type: str

    file_name: str

    file_size: int

    status: str

    match_score: Optional[float] = None

    ocr_verified: Optional[int] = None

    uploaded_at: datetime

    reviewed_at: Optional[datetime] = None

    admin_remarks: Optional[str] = None

    failed_reasons: List[str] = []


# =========================================================
# ALL DOCUMENTS RESPONSE
# =========================================================
class AllDocumentsResponse(BaseModel):

    user_id: int

    email: str

    documents: List[DocumentListItem]

    total_documents: int

    required_documents: List[str]

    missing_documents: List[str]

    all_approved: bool


# ── Admin ────────────────────────────────────────────────

class DocumentApprovalRequest(BaseModel):

    document_id: int

    status: DocumentStatusEnum

    admin_remarks: Optional[str] = None


class DocumentApprovalResponse(BaseModel):

    message: str

    document_id: int

    new_status: str

    user_email: str

    user_kyc_status: str


class PendingDocumentItem(BaseModel):

    id: int

    user_id: int

    email: str

    document_type: str

    file_name: str

    file_path: str

    file_size: int

    match_score: Optional[float] = None

    uploaded_at: str

    status: str


class PendingDocumentsResponse(BaseModel):

    pending_documents: List[PendingDocumentItem]

    total_pending: int


class DocumentReviewResponse(BaseModel):

    document_id: int

    document_type: str

    user_email: str

    status: str

    message: str

    kyc_completed: bool = False


class UserKYCDetails(BaseModel):

    user_id: int

    email: str

    full_name: str

    pan_number: str

    aadhaar_number: str

    pan_status: str

    aadhaar_status: str

    bank_status: str

    document_status: str

    kyc_status: str

    created_at: datetime

    pan_verified_at: Optional[datetime] = None

    aadhaar_verified_at: Optional[datetime] = None

    bank_verified_at: Optional[datetime] = None