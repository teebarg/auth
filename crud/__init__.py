from typing import Any, Dict, Union

from fastapi.encoders import jsonable_encoder
from sqlmodel import Session, select

from models.user import User, UserUpdate

from .user import user  # noqa: F401


# For a new basic set of CRUD operations you could just do
def update_or_create_user(
    *,
    db: Session,
    obj_in: Union[UserUpdate, Dict[str, Any]],
    email: str,
) -> User:
    update_data = {}
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.dict(exclude_unset=True)

    if model := db.exec(select(User).where(User.email == email)).first():
        obj_data = jsonable_encoder(model)
        for field in obj_data:
            if field in update_data:
                setattr(model, field, update_data[field])
    else:
        # If the record doesn't exist, create a new record
        update_data["email"] = email
        model = User(**update_data)
        db.add(model)

    db.commit()
    db.refresh(model)
    return model
