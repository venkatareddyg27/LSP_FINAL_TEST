from fastapi import (
    HTTPException,
    BackgroundTasks
)

import requests

from sqlalchemy.orm import Session

from datetime import datetime
from decimal import Decimal

from models.Loan_application.loan_application import (
    LoanApplication
)

from models.Loan_application.loan_transaction import (
    LoanTransaction
)

from models.Esign.agreements import (
    Agreement
)

from services.payment.razorpay_service import (
    RazorpayService
)

from repositories.Loan_application.loan_disbursement_repo import (
    LoanDisbursementRepository
)

from repositories.Loan_application.loan_transaction_repo import (
    LoanTransactionRepository
)

from core.enums import (
    LoanApplicationStatus,
    DisbursementStatusEnum,
    PaymentModeEnum,
    enum_value
)

from core.config import settings
from core.email_service import EmailService
from core.logger import logger


# =====================================================
# PAYMENT METHOD MATCH
# =====================================================
def match_payment_method(
    b,
    payment_mode
):

    if getattr(
        b,
        "status",
        None
    ) != "VERIFIED":

        return False

    if payment_mode.value == "BANK":

        return bool(
            getattr(
                b,
                "account_number",
                None
            )
        )

    if payment_mode.value == "UPI":

        return bool(
            getattr(
                b,
                "upi_id",
                None
            )
        )

    return False


# =====================================================
# DISBURSEMENT SERVICE
# =====================================================
class LoanDisbursementService:

    @staticmethod
    def disburse_loan(
        db: Session,
        application_id: int,
        payment_mode: PaymentModeEnum,
        background_tasks: BackgroundTasks | None = None
    ):

        try:

            logger.info(
                f"[DISBURSEMENT START] "
                f"application_id={application_id}"
            )

            # =========================================
            # LOCK APPLICATION
            # =========================================
            application = (
                db.query(LoanApplication)
                .filter(
                    LoanApplication.id
                    == application_id
                )
                .with_for_update()
                .first()
            )

            if not application:

                raise HTTPException(
                    404,
                    "Application not found"
                )

            logger.info(
                f"[APPLICATION STATUS] "
                f"{application.application_status}"
            )

            # =========================================
            # CHECK EXISTING DISBURSEMENT
            # =========================================
            existing = (
                LoanDisbursementRepository
                .get_by_application_id(
                    db,
                    application.id
                )
            )

            if (
                existing
                and existing.payment_status
                == DisbursementStatusEnum.SUCCESS
            ):

                raise HTTPException(
                    400,
                    "Loan already disbursed"
                )

            # =========================================
            # VALIDATE E-SIGN COMPLETION
            # =========================================
            agreement = (
                db.query(Agreement)
                .filter(
                    Agreement.application_id
                    == application.id,

                    Agreement.is_active == True
                )
                .first()
            )

            if not agreement:

                raise HTTPException(
                    404,
                    "Agreement not found"
                )

            if agreement.esign_status != "SIGNED":

                raise HTTPException(
                    400,
                    "Please complete e-sign before disbursement"
                )

            logger.info(
                f"[ESIGN VERIFIED] "
                f"application={application.id}"
            )

            # =========================================
            # USER PROFILE
            # =========================================
            profile = application.user_profile

            if not profile:

                raise HTTPException(
                    404,
                    "User profile not found"
                )

            user = profile.user

            # =========================================
            # VERIFIED PAYMENT METHOD
            # =========================================
            payout_method = next(
                (
                    b for b
                    in profile.bank_verifications

                    if match_payment_method(
                        b,
                        payment_mode
                    )
                ),
                None
            )

            if not payout_method:

                raise HTTPException(
                    400,
                    "No verified payout method"
                )

            # =========================================
            # DISBURSEMENT AMOUNT
            # =========================================
            if not application.disbursed_amount:

                raise HTTPException(
                    400,
                    "Disbursement amount not available"
                )

            net_amount = float(
                application.disbursed_amount
            )

            logger.info(
                f"[DISBURSE AMOUNT] "
                f"Rs.{net_amount}"
            )

            # =========================================
            # MOCK PAYOUT
            # =========================================
            if getattr(
                settings,
                "USE_MOCK_PAYOUT",
                False
            ):

                logger.info(
                    "[MOCK PAYOUT] "
                    "Using test mode"
                )

                payout = {

                    "success": True,

                    "payout_id": (
                        f"mock_"
                        f"{application.id}_"
                        f"{int(datetime.utcnow().timestamp())}"
                    ),

                    "status": "success"
                }

            # =========================================
            # LIVE PAYOUT
            # =========================================
            else:

                razorpay = RazorpayService()

                payout = (
                    razorpay.process_payout(
                        name=profile.full_name,

                        account_number=(
                            payout_method
                            .account_number
                        ),

                        ifsc=(
                            payout_method.ifsc
                        ),

                        amount=net_amount,

                        email=profile.email,

                        phone=user.mobile_number
                    )
                )

            # =========================================
            # PAYOUT FAILURE
            # =========================================
            if not payout.get("success"):

                raise HTTPException(
                    500,
                    payout.get(
                        "error",
                        "Payout failed"
                    )
                )

            payout_id = payout.get(
                "payout_id"
            )

            logger.info(
                f"[PAYOUT SUCCESS] "
                f"{payout_id}"
            )

            # =========================================
            # DETERMINE STATUS
            # =========================================
            if getattr(
                settings,
                "USE_MOCK_PAYOUT",
                False
            ):

                payment_status = (
                    DisbursementStatusEnum
                    .SUCCESS
                )

                application_status = (
                    LoanApplicationStatus
                    .ACTIVE
                )

                current_step = "ACTIVE"

            else:

                payment_status = (
                    DisbursementStatusEnum
                    .PROCESSING
                )

                application_status = (
                    LoanApplicationStatus
                    .DISBURSEMENT_INITIATED
                )

                current_step = (
                    "DISBURSEMENT_INITIATED"
                )

            # =========================================
            # SAVE DISBURSEMENT
            # =========================================
            disbursement = (
                LoanDisbursementRepository
                .upsert(
                    db,
                    application_id=application.id,
                    data={

                        "amount": Decimal(
                            str(net_amount)
                        ),

                        "payment_mode": (
                            payment_mode
                        ),

                        "payment_status": (
                            payment_status
                        ),

                        "payment_reference_id": (
                            payout_id
                        )
                    }
                )
            )

            # =========================================
            # SAVE TRANSACTION
            # =========================================
            transaction = LoanTransaction(

                application_id=application.id,

                disbursement_id=(
                    disbursement.id
                ),

                transaction_type=(
                    "DISBURSEMENT"
                ),

                amount=Decimal(
                    str(net_amount)
                ),

                status=payment_status.value,

                payment_mode=(
                    payment_mode.value
                ),

                remarks=(
                    "Disbursement initiated"
                )
            )

            LoanTransactionRepository.create(
                db,
                transaction
            )

            # =========================================
            # UPDATE APPLICATION
            # =========================================
            application.application_status = (
                enum_value(
                    application_status
                )
            )

            application.payout_status = (
                payment_status
            )

            application.current_step = (
                current_step
            )

            application.disbursed_at = (
                datetime.utcnow()
            )

            application.updated_at = (
                datetime.utcnow()
            )

            db.add(application)

            # =========================================
            # COMMIT
            # =========================================
            db.commit()

            db.refresh(application)

            db.refresh(disbursement)

            logger.info(
                f"[DISBURSEMENT SUCCESS] "
                f"application={application.id}, "
                f"status={application.application_status}, "
                f"payout_id={payout_id}"
            )

        except HTTPException:

            db.rollback()

            raise

        except Exception as e:

            import traceback

            db.rollback()

            traceback.print_exc()

            logger.error(
                f"[DISBURSE ERROR] "
                f"{str(e)}"
            )

            raise HTTPException(
                500,
                f"Disbursement failed: "
                f"{str(e)}"
            )

        # =============================================
        # EMAIL
        # =============================================
        try:

            email_body = f"""
            Dear {profile.full_name},

            Your loan disbursement has been initiated successfully.

            Amount: Rs.{net_amount}
            Application ID: {application.id}

            Current Status: {payment_status.value}

            Thank you.
            """

            if background_tasks:

                background_tasks.add_task(
                    EmailService.send_email,
                    profile.email,
                    "Loan Disbursement Initiated",
                    email_body
                )

            else:

                EmailService.send_email(
                    profile.email,
                    "Loan Disbursement Initiated",
                    email_body
                )

            logger.info(
                f"[EMAIL SENT] "
                f"{profile.email}"
            )

        except Exception as e:

            logger.error(
                f"[EMAIL ERROR] "
                f"{str(e)}"
            )

        # =============================================
        # TRACKING CALLBACK
        # =============================================
        try:

            if getattr(
                settings,
                "TRACKING_URL",
                None
            ):

                requests.post(
                    settings.TRACKING_URL,
                    json={
                        "application_id": (
                            application.id
                        ),

                        "status": (
                            payment_status.value
                        )
                    },
                    timeout=5
                )

        except Exception as e:

            logger.error(
                f"[TRACKING ERROR] "
                f"{str(e)}"
            )

        # =============================================
        # RESPONSE
        # =============================================
        return {

            "id": (
                disbursement.id
            ),

            "application_id": (
                application.id
            ),

            "amount": float(
                disbursement.amount
            ),

            "payment_mode": (
                disbursement.payment_mode.value

                if hasattr(
                    disbursement.payment_mode,
                    "value"
                )

                else str(
                    disbursement.payment_mode
                )
            ),

            "payment_status": (

                disbursement.payment_status.value

                if hasattr(
                    disbursement.payment_status,
                    "value"
                )

                else str(
                    disbursement.payment_status
                )
            ),

            "payout_id": payout_id,

            "payout_status": (
                application.payout_status
            ),

            "application_status": (
                application.application_status
            ),

            "current_step": (
                application.current_step
            ),

            "message": (
                "Disbursement completed successfully"

                if payment_status
                == DisbursementStatusEnum.SUCCESS

                else

                "Disbursement initiated successfully"
            )
        }