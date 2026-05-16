import os
from sqlalchemy.orm import Session

from models.Auth.user import User
from core.security import hash_password


def create_default_super_admin(
    db: Session,
    username: str = None,
    mobile_number: str = None,
    password: str = None,
    device_id: str = None
):
    try:
        username = username or os.getenv("SUPER_ADMIN_NAME", "superadmin")
        mobile_number = mobile_number or os.getenv("SUPER_ADMIN_MOBILE", "9999999999")
        password = (password or os.getenv("SUPER_ADMIN_PASSWORD", "Admin@123"))[:72]
        device_id = device_id or os.getenv("SUPER_ADMIN_DEVICE_ID", "SUPERADMIN_DEVICE")

        print("Checking existing super admin...")

        existing = db.query(User).filter(
            User.role == "SUPER_ADMIN"
        ).first()

        if existing:
            print("✅ SUPER ADMIN ALREADY EXISTS")
            return existing

        print("Creating new super admin...")

        super_admin = User(
            username=username,
            mobile_number=mobile_number,
            password_hash=hash_password(password),
            device_id=device_id,
            role="SUPER_ADMIN",
            is_active=True,
            is_verified=True
        )

        db.add(super_admin)
        db.commit()
        db.refresh(super_admin)

        print("✅ SUPER ADMIN CREATED")
        return super_admin

    except Exception as e:
        db.rollback()
        print("❌ SUPER ADMIN ERROR:", repr(e))
        raise e