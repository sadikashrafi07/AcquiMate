from fastapi import HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from . import models, schemas

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(pw: str) -> str:
    return pwd_ctx.hash(pw)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    existing = get_user_by_email(db, user.email)
    if existing:
        raise HTTPException(400, "Email already registered")
    hashed = get_password_hash(user.password)
    db_user = models.User(name=user.name, email=user.email, password=hashed)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, user: schemas.UserLogin):
    db_user = get_user_by_email(db, user.email)
    if not db_user:
        raise HTTPException(400, "Invalid credentials")
    # For OAuth users, we'll use a special prefix in the password
    if db_user.password.startswith("oauth_"):
        raise HTTPException(400, "This account uses Google login. Please login with Google.")
    if not verify_password(user.password, db_user.password):
        raise HTTPException(400, "Invalid credentials")
    return db_user

def create_oauth_user(db: Session, email: str, name: str):
    # Instead of using an is_oauth_user field, we'll use a special password format
    db_user = models.User(
        email=email,
        name=name,
        password="oauth_user"  # Special prefix to identify OAuth users
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user