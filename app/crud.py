from fastapi import HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from . import models, schemas
import os
import shutil
from fastapi import UploadFile
import uuid

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
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check if passwords match
    if user.password != user.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
        
    hashed = get_password_hash(user.password)
    db_user = models.User(name=user.name, email=user.email, password=hashed)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, user: schemas.UserLogin):
    db_user = get_user_by_email(db, user.email)
    if not db_user:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    # For OAuth users, we'll use a special prefix in the password
    if db_user.password.startswith("oauth_"):
        raise HTTPException(status_code=400, detail="This account uses Google login. Please login with Google.")
    
    if not verify_password(user.password, db_user.password):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    return db_user

def create_oauth_user(db: Session, email: str, name: str):
    # Check if user already exists
    existing = get_user_by_email(db, email)
    if existing:
        # If user exists but is not an OAuth user, don't overwrite their account
        if not existing.password.startswith("oauth_"):
            raise HTTPException(status_code=400, detail="Email already registered with password authentication")
        return existing
        
    # Create new OAuth user
    db_user = models.User(
        email=email,
        name=name,
        password="oauth_user"  # Special prefix to identify OAuth users
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user_by_id(db: Session, user_id: int):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return None
    
    return user

def update_user_profile(db: Session, user_id: int, user_data: schemas.UserProfileUpdate):
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Only update email if it's different and not already taken by another user
    if user_data.email != db_user.email:
        existing = get_user_by_email(db, user_data.email)
        if existing and existing.id != user_id:
            raise HTTPException(status_code=400, detail="Email already registered to another account")
    
    # Update user fields
    db_user.name = user_data.username
    db_user.email = user_data.email
    
    # Update optional fields if provided
    if user_data.first_name is not None:
        db_user.first_name = user_data.first_name
    
    if user_data.last_name is not None:
        db_user.last_name = user_data.last_name
    
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_password(db: Session, user_id: int, password: str):
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user is OAuth user
    if db_user.password.startswith("oauth_"):
        raise HTTPException(status_code=400, detail="Cannot update password for OAuth users")
    
    # Update password
    db_user.password = get_password_hash(password)
    
    db.commit()
    db.refresh(db_user)
    return db_user

def save_profile_image(user_id: int, file: UploadFile) -> str:
    # Create uploads directory if it doesn't exist
    upload_dir = os.path.join("static", "uploads", "profiles")
    os.makedirs(upload_dir, exist_ok=True)
    
    # Generate unique filename
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{user_id}_{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(upload_dir, unique_filename)
    
    # Save file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Return relative path for database storage
    return f"/static/uploads/profiles/{unique_filename}"

def update_user_profile_image(db: Session, user_id: int, profile_image_path: str):
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Delete old profile image if exists
    if db_user.profile_image and os.path.exists(db_user.profile_image.lstrip("/")):
        try:
            os.remove(db_user.profile_image.lstrip("/"))
        except:
            pass  # Ignore errors when removing old file
    
    # Update profile image path
    db_user.profile_image = profile_image_path
    
    db.commit()
    db.refresh(db_user)
    return db_user