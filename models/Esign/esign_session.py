from sqlalchemy import (
    Column,
    BigInteger,
    String,
    DateTime,
    JSON,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Boolean,
    Text
)

from sqlalchemy.sql import func

from sqlalchemy.orm import relationship

from enum import Enum

from core.database import Base


# =====================================================
# ESIGN STATUS
# =====================================================
class EsignStatus(str, Enum):

    INITIATED = "INITIATED"

    OTP_SENT = "OTP_SENT"

    IN_PROGRESS = "IN_PROGRESS"

    SIGNED = "SIGNED"

    FAILED = "FAILED"

    EXPIRED = "EXPIRED"


# =====================================================
# ESIGN SESSION
# =====================================================
class EsignSession(Base):

    __tablename__ = "esign_sessions"

    # =================================================
    # PRIMARY KEY
    # =================================================
    id = Column(
        BigInteger,
        primary_key=True,
        index=True
    )

    # =================================================
    # FOREIGN KEYS
    # =================================================
    application_id = Column(
        BigInteger,
        ForeignKey(
            "loan_application.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    agreement_id = Column(
        BigInteger,
        ForeignKey(
            "agreements.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    user_id = Column(
        BigInteger,
        nullable=False,
        index=True
    )

    # =================================================
    # ACTIVE SESSION
    # =================================================
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True
    )

    # =================================================
    # PROVIDER TRANSACTION
    # =================================================
    transaction_id = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    provider = Column(
        String,
        nullable=True
    )

    provider_document_id = Column(
        String,
        nullable=True,
        index=True
    )

    # =================================================
    # SIGNER DETAILS
    # =================================================
    signer_name = Column(
        String,
        nullable=True
    )

    signer_mobile = Column(
        String,
        nullable=True
    )

    masked_aadhaar = Column(
        String,
        nullable=True
    )

    # =================================================
    # PAYLOAD TRACKING
    # =================================================
    request_payload = Column(
        JSON,
        nullable=False
    )

    response_payload = Column(
        JSON,
        nullable=True
    )

    callback_payload = Column(
        JSON,
        nullable=True
    )

    # =================================================
    # STATUS
    # =================================================
    status = Column(
        SqlEnum(EsignStatus),
        default=EsignStatus.INITIATED,
        nullable=False,
        index=True
    )

    # =================================================
    # SIGNED DOCUMENT
    # =================================================
    signed_pdf_path = Column(
        String,
        nullable=True
    )

    signed_file_hash = Column(
        String,
        nullable=True
    )

    # =================================================
    # CALLBACK PROCESSING
    # =================================================
    callback_processed = Column(
        Boolean,
        default=False,
        nullable=False
    )

    callback_received_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    # =================================================
    # FAILURE DETAILS
    # =================================================
    failure_reason = Column(
        Text,
        nullable=True
    )

    # =================================================
    # TIMESTAMPS
    # =================================================
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now()
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    signed_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    # =================================================
    # RELATIONSHIPS
    # =================================================
    agreement = relationship(
        "Agreement",
        back_populates="esign_sessions"
    )

    signed_document = relationship(
        "SignedDocument",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan"
    )

    audit_logs = relationship(
        "EsignAuditLog",
        back_populates="session",
        cascade="all, delete-orphan"
    )

    # =================================================
    # INDEXES
    # =================================================
    __table_args__ = (

        Index(
            "idx_esign_app_status",
            "application_id",
            "status"
        ),

        Index(
            "idx_esign_agreement_active",
            "agreement_id",
            "is_active"
        ),

        Index(
            "idx_esign_provider_txn",
            "provider",
            "transaction_id"
        ),
    )