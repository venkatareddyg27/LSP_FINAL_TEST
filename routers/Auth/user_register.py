from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from core.database import get_db
from models.Auth.user import User
from models.Auth.user_device import UserDevice
from core.security import (
    hash_password,
    create_access_token,
    create_refresh_token
)
from datetime import datetime, timedelta
from models.Auth.user_session import UserSession
from core.validators import (
    validate_mobile_number,
    validate_password
)
from schemas.Auth.RegisterSchema import RegisterSchema
from schemas.Auth.SendOTPSchema import (
    VerifyOTPSchema,
    ResendOTPSchema
)
from services.Auth.otp_services import (
    send_otp,
    resend_otp,
    verify_otp,
    PURPOSE_REGISTER
)
from models.Auth.otp_verification import OTPVerification

router = APIRouter(
    prefix="/auth",
    tags=["User Registration Process"]
)

# =====================================================
# REGISTER → SEND OTP
# =====================================================
@router.post("/register")
def register_and_send_otp(
    data: RegisterSchema,
    db: Session = Depends(get_db),
):

    mobile = validate_mobile_number(data.mobile_number)

    validate_password(data.password)

    # ✅ DEBUG LOGS
    print("\n========== REGISTER API HIT ==========", flush=True)
    print(f"Mobile Number : {mobile}", flush=True)
    print(f"Device ID     : {data.device_id}", flush=True)
    print("======================================\n", flush=True)

    # =================================================
    # CHECK IF USER EXISTS
    # =================================================
    existing_user = (
        db.query(User)
        .filter(
            User.mobile_number == mobile
        )
        .first()
    )

    # =================================================
    # EXISTING USER CHECKS
    # =================================================
    if existing_user:

        # Same device
        if existing_user.device_id == data.device_id:

            if existing_user.is_verified:

                raise HTTPException(
                    status_code=409,
                    detail="User already registered and verified on this device"
                )

            raise HTTPException(
                status_code=400,
                detail="User already registered. Please verify OTP"
            )

        # Different device
        raise HTTPException(
            status_code=403,
            detail="This mobile number is already registered on another device"
        )

    # =================================================
    # SEND OTP
    # =================================================
    print("Calling send_otp service...", flush=True)

    send_otp(
        db=db,
        username=data.username,
        password=data.password,
        device_id=data.device_id,
        mobile_number=mobile,
        purpose=PURPOSE_REGISTER,
    )

    print("OTP service completed successfully", flush=True)

    return {
        "message": "OTP sent successfully",
        "next": "verify_otp",
    }

# =====================================================
# VERIFY OTP → ACTIVATE USER
# =====================================================
@router.post("/register/verify-otp")
def verify_register_otp(
    data: VerifyOTPSchema,
    db: Session = Depends(get_db),
):

    mobile = validate_mobile_number(data.mobile_number)

    print("\n========== VERIFY OTP API HIT ==========", flush=True)
    print(f"Mobile : {mobile}", flush=True)
    print("========================================\n", flush=True)

    # =================================================
    # VERIFY OTP
    # =================================================
    verify_otp(
        db=db,
        mobile_number=mobile,
        otp=data.otp,
        device_id=data.device_id,
        purpose=PURPOSE_REGISTER,
    )

    # =================================================
    # FETCH VERIFIED OTP
    # =================================================
    otp_row = (
        db.query(OTPVerification)
        .filter(
            OTPVerification.mobile_number == mobile,
            OTPVerification.purpose == PURPOSE_REGISTER,
            OTPVerification.otp_status == "VERIFIED",
        )
        .order_by(OTPVerification.id.desc())
        .first()
    )

    if not otp_row:
        raise HTTPException(
            status_code=400,
            detail="OTP verification failed"
        )

    if otp_row.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=400,
            detail="OTP expired"
        )

    # =================================================
    # FETCH USER
    # =================================================
    user = (
        db.query(User)
        .filter(User.id == otp_row.user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    if user.is_verified:
        raise HTTPException(
            status_code=409,
            detail="User already verified"
        )

    # =================================================
    # ACTIVATE USER
    # =================================================
    user.is_verified = True
    user.is_active = True

    db.commit()

    # =================================================
    # REGISTER DEVICE
    # =================================================
    db.add(
        UserDevice(
            user_id=user.id,
            device_id=otp_row.device_id,
            created_at=datetime.utcnow(),
        )
    )

    db.commit()

    db.refresh(user)

    # =================================================
    # TOKENS
    # =================================================
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "role": user.role
        }
    )

    refresh_token = create_refresh_token(
        data={
            "sub": str(user.id),
            "role": user.role
        }
    )

    print("User registration completed successfully", flush=True)

    return {
        "message": "User registered successfully",
        "user_id": user.id,
        "access_token": access_token,
        "refresh_token": refresh_token,
    }

# =====================================================
# RESEND REGISTER OTP
# =====================================================
@router.post("/register/resend-otp")
def resend_register_otp(
    data: ResendOTPSchema,
    db: Session = Depends(get_db),
):

    mobile = validate_mobile_number(data.mobile_number)

    print("\n========== RESEND OTP API HIT ==========", flush=True)
    print(f"Mobile : {mobile}", flush=True)
    print("========================================\n", flush=True)

    resend_otp(
        db=db,
        mobile_number=mobile,
        device_id=data.device_id,
        purpose=PURPOSE_REGISTER,
    )

    return {
        "message": "OTP resent successfully"
    }