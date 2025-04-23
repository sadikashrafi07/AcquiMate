from pydantic import BaseModel, EmailStr, field_validator

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