from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from fastapi import UploadFile, File

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    confirm_password: str
    
    @field_validator("confirm_password")
    def passwords_match(cls, v, values):
        if 'password' in values.data and values.data["password"] != v:
            raise ValueError("Passwords do not match")
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr

    class Config:
        from_attributes = True  # pydantic v2 replacement for orm_mode

class UserProfileUpdate(BaseModel):
    username: str
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class UserPasswordUpdate(BaseModel):
    password: Optional[str] = None
    
    @field_validator("password")
    def password_not_empty(cls, v):
        if v and len(v) < 1:
            raise ValueError("Password cannot be empty if provided")
        return v