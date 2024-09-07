from typing import Any, Dict

from sqlmodel import Session, select

from core.security import get_password_hash, verify_password
from crud.base import CRUDBase
from models.user import User, UserCreate, UserUpdate
import logging


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    def create(self, db: Session, user_create: UserCreate) -> User:
        db_obj = User.model_validate(
            user_create,
            update={"hashed_password": get_password_hash(user_create.password)},
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def authenticate(self, *, db: Session, email: str, password: str) -> User | None:
        db_user = self.get_user_by_email(db=db, email=email)
        if not db_user:
            return None
        if not verify_password(password, db_user.hashed_password):
            return None
        return db_user

    def get_user_by_email(self, *, db: Session, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        return db.exec(statement).first()

    def update(self, *, db: Session, db_obj: User, user_in: UserUpdate) -> User:
        user_data = user_in.model_dump(exclude_unset=True)
        extra_data = {}
        if "password" in user_data:
            password = user_data["password"]
            hashed_password = get_password_hash(password)
            extra_data["hashed_password"] = hashed_password
        db_obj.sqlmodel_update(user_data, update=extra_data)
        return self.sync(db=db, update=db_obj, type="update")

    def is_active(self, user: User) -> bool:
        return user.is_active

    def is_superuser(self, user: User) -> bool:
        return user.is_superuser

    def update_or_create(
        self,
        db: Session,
        *,
        obj_in: UserUpdate,
        column_name: str,
        column_value: str,
    ) -> User:
        update_data = obj_in.model_dump(exclude_unset=True)
        if model := db.exec(
            select(User).where(getattr(User, column_name) == column_value)
        ).first():
            model.sqlmodel_update(update_data)
        else:
            # If the record doesn't exist, create a new record
            update_data[column_name] = column_value
            model = User(**update_data)
            db.add(model)

        db.commit()
        db.refresh(model)
        return model

    async def bulk_upload(self, db: Session, *, users: list[Dict[str, Any]]) -> User:
        for user in users:
            try:
                if model := db.exec(
                    select(User).where(User.email == user.get("email"))
                ).first():
                    model.sqlmodel_update(user)
                else:
                    model = User(**user)
                    db.add(model)
                db.commit()
            except Exception as e:
                logging.error(e)


user = CRUDUser(User)
