"""Manual provisioning only: python bootstrap_admin.py (after migration)."""
import os
from dotenv import load_dotenv
load_dotenv()
from pydantic import TypeAdapter, EmailStr
from sqlalchemy import func
from models.user import SessionLocal, User
from routes.auth import pwd_context


def bootstrap(email, password):
    email = str(TypeAdapter(EmailStr).validate_python(email))
    if (len(password) < 12 or len(password.encode()) > 72 or
        not any(c.isupper() for c in password) or not any(c.islower() for c in password) or
        not any(c.isdigit() for c in password) or not any(not c.isalnum() for c in password)):
        raise ValueError("Password requires 12+ characters, upper/lowercase, digit, symbol and at most 72 UTF-8 bytes")
    with SessionLocal() as db:
        user = db.query(User).filter(func.lower(User.email) == email.lower()).first()
        if user:
            if user.role == "SYSTEM_ADMIN" and user.is_active:
                return "Administrator already provisioned; password unchanged"
            raise ValueError("Existing non-admin or inactive account; refusing automatic promotion")
        db.add(User(email=email.lower(), hashed_password=pwd_context.hash(password), role="SYSTEM_ADMIN"))
        db.commit()
    return "Administrator provisioned"


if __name__ == "__main__":
    try:
        print(bootstrap(os.environ["ADMIN_BOOTSTRAP_EMAIL"], os.environ["ADMIN_BOOTSTRAP_PASSWORD"]))
    except Exception:
        raise SystemExit("Bootstrap failed; check private variables, account conflict and migrated database. No credentials printed.")
