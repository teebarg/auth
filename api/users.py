from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query
)
from sqlmodel import func, or_, select

import crud
from core import deps
from core.config import settings
from core.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)
from core.security import get_password_hash, verify_password
from core.utils import (
    generate_new_account_email,
    send_email,
)
from models.message import Message
from models.user import (
    UpdatePassword,
    User,
    UserCreate,
    UserPublic,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)

# Create a router for users
router = APIRouter()


@router.get("/admin-me")
async def read_admin(admin_user: deps.AdminUser) -> User:
    """
    Get current admin user.
    """
    return admin_user  # type: ignore


@router.get("/me")
async def read_user_me(current_user: deps.CurrentUser) -> UserPublic:
    """
    Get current user.
    """
    return current_user  # type: ignore


@router.get(
    "/",
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


@router.post(
    "/", dependencies=[Depends(get_current_active_superuser)], response_model=UserPublic
)
def create_user(*, db: SessionDep, user_in: UserCreate) -> Any:
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
            email_to=user_in.email, username=user_in.email, password=user_in.password
        )
        send_email(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return user


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, db: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """

    if user_in.email:
        existing_user = crud.user.get_user_by_email(db=db, email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    current_user = crud.user.update(db=db, db_obj=current_user, obj_in=user_in)
    return current_user


@router.patch("/me/password")
def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )
    hashed_password = get_password_hash(body.new_password)
    current_user.hashed_password = hashed_password
    session.add(current_user)
    session.commit()
    return {"message": "Password updated successfully"}


@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: int, session: SessionDep, current_user: CurrentUser
) -> Any:
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


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
def update_user(
    *,
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


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
def delete_user(db: SessionDep, current_user: CurrentUser, user_id: int) -> Message:
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

