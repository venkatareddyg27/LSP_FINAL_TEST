from pydantic import BaseModel, Field
from typing import Optional


class AgreementRequest(BaseModel):
    loan_id: int = Field(..., gt=0)


class AgreementResponse(BaseModel):

    exists: bool

    loan_id: int

    pdf_path: Optional[str] = None

    status: str

    signed_pdf_path: Optional[str] = None

    message: Optional[str] = None