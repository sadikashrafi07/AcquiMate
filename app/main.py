from fastapi import FastAPI, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv

from . import models, schemas, crud
from .database import engine, get_db
from .oauth import login_via_google, auth_google_callback

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

# Try to mount static files if the directory exists
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
async def index(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/", status_code=303)
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
        return RedirectResponse("/index", status_code=303)
    except HTTPException as e:
        return templates.TemplateResponse("login.html", {"request": request, "error": e.detail})