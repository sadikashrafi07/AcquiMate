from fastapi import FastAPI, Depends, Request, Form, HTTPException, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
import os
from typing import Optional
from dotenv import load_dotenv

from . import models, schemas, crud
from .database import engine, get_db
from .oauth import login_via_google, auth_google_callback

# Load environment variables
load_dotenv()

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Add session middleware with secure key from environment
app.add_middleware(
    SessionMiddleware, 
    secret_key=os.getenv("SECRET_KEY", "your-secret-key")
)

# Templates directory
templates = Jinja2Templates(directory="templates")

# Mount static files
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except:
    pass  # Ignore if static directory doesn't exist

@app.get("/", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        user = crud.authenticate_user(db, schemas.UserLogin(email=email, password=password))
        request.session["user"] = {"id": user.id, "name": user.name, "email": user.email}
        
        # Add profile image to session if it exists
        if user.profile_image:
            request.session["user"]["profile_image"] = user.profile_image
            
        return RedirectResponse("/index", status_code=303)  # 303 See Other for POST → GET
    except HTTPException as e:
        return templates.TemplateResponse("login.html", {"request": request, "error": e.detail})

@app.get("/signup", response_class=HTMLResponse)
async def signup_get(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@app.post("/signup")
async def signup_post(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        crud.create_user(db, schemas.UserCreate(
            name=name, 
            email=email, 
            password=password, 
            confirm_password=confirm_password
        ))
        return RedirectResponse("/", status_code=303)  # 303 See Other for POST → GET
    except HTTPException as e:
        return templates.TemplateResponse("signup.html", {"request": request, "error": e.detail})
    except Exception as e:
        return templates.TemplateResponse("signup.html", {"request": request, "error": str(e)})

@app.get("/index", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/", status_code=303)
    
    # Get the full user object from database to ensure we have the latest data
    if "id" in user:
        db_user = crud.get_user_by_id(db, user["id"])
        if db_user:
            # Update session with latest user data
            user_data = {
                "id": db_user.id,
                "name": db_user.name,
                "email": db_user.email
            }
            
            # Add profile image to session if it exists
            if db_user.profile_image:
                user_data["profile_image"] = db_user.profile_image
                
            # Update the session with fresh data
            request.session["user"] = user_data
            
            return templates.TemplateResponse("index.html", {"request": request, "user": user_data})
    
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse("/", status_code=303)

@app.get("/auth/google")
async def google_login(request: Request):
    return await login_via_google(request)

@app.get("/auth/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        user = await auth_google_callback(request, db)
        request.session["user"] = {"id": user.id, "name": user.name, "email": user.email}
        
        # Add profile image to session if it exists
        if hasattr(user, 'profile_image') and user.profile_image:
            request.session["user"]["profile_image"] = user.profile_image
            
        return RedirectResponse("/index", status_code=303)
    except HTTPException as e:
        return templates.TemplateResponse("login.html", {"request": request, "error": e.detail})

@app.get("/update-profile", response_class=HTMLResponse)
async def update_profile_get(request: Request, db: Session = Depends(get_db)):
    user_session = request.session.get("user")
    if not user_session:
        return RedirectResponse("/", status_code=303)
    
    # Get full user details from database
    user_id = user_session["id"]
    try:
        user = crud.get_user_by_id(db, user_id)
        if not user:
            return RedirectResponse("/logout", status_code=303)
            
        # Check if OAuth user
        is_oauth_user = user.password.startswith("oauth_")
        
        return templates.TemplateResponse(
            "update_profile.html", 
            {"request": request, "user": user, "is_oauth_user": is_oauth_user}
        )
    except Exception as e:
        # Fallback to showing a basic profile page
        return templates.TemplateResponse(
            "update_profile.html", 
            {
                "request": request, 
                "user": user_session, 
                "is_oauth_user": False,
                "error": True,
                "message": f"Error loading profile: {str(e)}"
            }
        )

@app.post("/update-profile")
async def update_profile_post(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    profile_picture: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    user_session = request.session.get("user")
    if not user_session:
        return RedirectResponse("/", status_code=303)
    
    user_id = user_session["id"]
    
    try:
        # First get the user to check if they exist and if they're OAuth
        db_user = crud.get_user_by_id(db, user_id)
        if not db_user:
            return RedirectResponse("/logout", status_code=303)
            
        is_oauth_user = db_user.password.startswith("oauth_")
        
        # Update profile data
        user_data = schemas.UserProfileUpdate(
            username=username,
            email=email,
            first_name=first_name if first_name else None,
            last_name=last_name if last_name else None
        )
        
        updated_user = crud.update_user_profile(db, user_id, user_data)
        
        # Update password if provided (and not OAuth user)
        if password and password.strip() and not is_oauth_user:
            crud.update_user_password(db, user_id, password)
        
        # Update profile image if provided
        if profile_picture and profile_picture.filename:
            profile_image_path = crud.save_profile_image(user_id, profile_picture)
            crud.update_user_profile_image(db, user_id, profile_image_path)
        
        # Get the final updated user with all changes
        final_user = crud.get_user_by_id(db, user_id)
        
        # Update session data
        session_data = {
            "id": final_user.id, 
            "name": final_user.name, 
            "email": final_user.email
        }
        
        # Add profile image to session if it exists
        if final_user.profile_image:
            session_data["profile_image"] = final_user.profile_image
            
        request.session["user"] = session_data
        
        # Return to the profile page with a success message
        # The page will handle redirect after showing the message
        return templates.TemplateResponse(
            "update_profile.html",
            {
                "request": request, 
                "user": final_user, 
                "message": "Profile updated successfully!", 
                "error": False, 
                "is_oauth_user": is_oauth_user
            }
        )
        
    except HTTPException as e:
        user = crud.get_user_by_id(db, user_id)
        is_oauth_user = user.password.startswith("oauth_") if user else False
        return templates.TemplateResponse(
            "update_profile.html", 
            {"request": request, "user": user, "message": e.detail, "error": True, "is_oauth_user": is_oauth_user}
        )
    except Exception as e:
        user = crud.get_user_by_id(db, user_id)
        is_oauth_user = user.password.startswith("oauth_") if user else False
        return templates.TemplateResponse(
            "update_profile.html", 
            {"request": request, "user": user, "message": str(e), "error": True, "is_oauth_user": is_oauth_user}
        )