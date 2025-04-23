import os
from typing import Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request
from starlette.config import Config
from . import models, crud

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configuration
config = Config(".env")
oauth = OAuth()

# Google OAuth setup
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

async def login_via_google(request: Request):
    redirect_uri = request.url_for("google_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)

async def auth_google_callback(request: Request, db: Session) -> Optional[models.User]:
    try:
        token = await oauth.google.authorize_access_token(request)
        
        # Extract user info from token
        if "userinfo" in token:
            user_info = token["userinfo"]
        else:
            # If userinfo is not directly in token, try to parse the ID token
            user_info = await oauth.google.parse_id_token(request, token)
            
        if not user_info:
            raise HTTPException(status_code=400, detail="Failed to fetch user info from Google")
            
        email = user_info.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email not provided by Google")
            
        name = user_info.get("name", "Google User")
        
        # Check if the user already exists
        db_user = crud.get_user_by_email(db, email)
        
        if db_user:
            # If user exists but wasn't an OAuth user (doesn't have oauth_ prefix), don't update
            return db_user
        else:
            # Create a new user with oauth prefix in password
            return crud.create_oauth_user(db, email, name)
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Google authentication failed: {str(e)}")