from sqlalchemy.orm import Session

from models.Auth.user import User

from core.security import hash_password
 
 
def create_default_super_admin(

    db: Session,

    username: str,

    mobile_number: str,

    password: str,

    device_id: str

):
 
    try:
 
        print("Checking existing super admin...")
 
        existing = db.query(User).filter(

            (User.mobile_number == mobile_number) |

            (User.username == username)

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
 
        print("Added to session")
 
        db.commit()
 
        print("Committed successfully")
 
        db.refresh(super_admin)
 
        print("✅ SUPER ADMIN CREATED")
 
        return super_admin
 
    except Exception as e:
 
        db.rollback()
 
        print("❌ SUPER ADMIN ERROR:", repr(e))
 
        raise e
 