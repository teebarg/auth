from datetime import timedelta
from core import deps, security
from core.deps import CurrentUser, SessionDep, get_current_active_superuser
import crud
from fastapi import FastAPI, Depends, HTTPException, Response, BackgroundTasks, Query
from typing import Any
from models.auth import SignIn, Social
import logging
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from core.utils import generate_new_account_email, send_email
from models.user import (
    User,
    UserCreate,
    UserPublic,
    UserRegister,
    UserUpdate,
    UsersPublic,
)
from sqlmodel import func, or_, select
from models.message import Message
from models.token import Token
from core.config import settings

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Welcome to the API"}


@app.post("/auth/login")
async def login(
    response: Response,
    db: deps.SessionDep,
    credentials: SignIn,
) -> UserPublic:
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

        return user
    except Exception as e:
        logging.error(e)
        raise HTTPException(
            status_code=500, detail=f"Error signing in. Error: ${e}"
        ) from e


@app.post("/auth/signup", response_model=UserPublic)
async def register(
    db: deps.SessionDep, user_in: UserRegister, background_tasks: BackgroundTasks
) -> Any:
    """
    Create new user without the need to be logged in.
    """
    try:
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
            firstname=user.firstname, email=user.email, password=user_in.password
        )
        background_tasks.add_task(
            send_email,
            email_to="neyostica2000@yahoo.com",
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
        return response
    except Exception as e:
        logging.error(e)
        raise HTTPException(
            status_code=500, detail=f"An error occurred while signing up. Error: ${e}"
        ) from e


@app.get("/auth/refresh-token", response_model=Token)
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
        logging.error(e)
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while refreshing token. Error: ${e}",
        ) from e


@app.post("/auth/social", response_model=Token)
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
        logging.error(e)
        raise HTTPException(
            status_code=500, detail=f"Error signing in user. Error: ${e}"
        ) from e


@app.get("/auth/logout")
async def logout(response: Response) -> Any:
    """
    Log out current user.
    """
    try:
        response.delete_cookie("access_token")
        return {"message": "Logged out successfully"}
    except Exception as e:
        logging.error(e)
        raise HTTPException(
            status_code=400, detail=f"Error signing out user. Error: ${e}"
        ) from e


@app.post(
    "/users",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
async def create_user(db: SessionDep, user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    user = crud.user.get_user_by_email(db=db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    user = crud.user.create(db=db, user_create=user_in)
    if settings.EMAILS_ENABLED and user_in.email:
        email_data = generate_new_account_email(
            firstname=user_in.firstname, email=user_in.email, password=user_in.password
        )
        send_email(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return user


@app.get("/users/me")
async def read_user_me(current_user: deps.CurrentUser) -> UserPublic:
    """
    Get current user.
    """
    return current_user  # type: ignore


@app.get(
    "/users",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
async def read_users(
    db: SessionDep,
    name: str = "",
    page: int = Query(default=1, gt=0),
    per_page: int = Query(default=20, le=100),
) -> Any:
    """
    Retrieve users.
    """

    query = {"firstname": name, "lastname": name}
    filters = crud.user.build_query(query)

    count_statement = select(func.count()).select_from(User)
    if filters:
        count_statement = count_statement.where(or_(*filters))
    total_count = db.exec(count_statement).one()

    users = crud.user.get_multi(
        db=db,
        filters=filters,
        per_page=per_page,
        offset=(page - 1) * per_page,
    )

    total_pages = (total_count // per_page) + (total_count % per_page > 0)

    return UsersPublic(
        data=users,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_count=total_count,
    )


@app.get("/users/{user_id}", response_model=UserPublic)
def get_user(user_id: int, session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Get a specific user by id.
    """
    user = session.get(User, user_id)
    if user == current_user:
        return user
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    return user


@app.patch(
    "/users/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
async def update_user(
    db: SessionDep,
    user_id: int,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """

    db_user = db.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    if user_in.email:
        existing_user = crud.user.get_user_by_email(db=db, email=user_in.email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )

    db_user = crud.user.update(db=db, db_obj=db_user, user_in=user_in)
    return db_user


# @app.patch("/users/{user_id}", response_model=User)
# async def update_user_password(user_id: int, password: str, db: Session = Depends(get_db)):
#     db_user = db.query(UserDB).filter(UserDB.id == user_id).first()
#     if db_user is None:
#         raise HTTPException(status_code=404, detail="User not found")
#     db_user.hashed_password = get_password_hash(password)
#     db.commit()
#     db.refresh(db_user)
#     return db_user


@app.delete("/users/{user_id}", dependencies=[Depends(get_current_active_superuser)])
async def delete_user(
    db: SessionDep, current_user: CurrentUser, user_id: int
) -> Message:
    """
    Delete a user.
    """
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    db.delete(user)
    db.commit()
    return Message(message="User deleted successfully")
