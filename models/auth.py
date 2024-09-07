import secrets

from sqlmodel import SQLModel


# JSON payload containing access token
class SignIn(SQLModel):
    email: str
    password: str


class Social(SQLModel):
    email: str
    firstname: str
    lastname: str
    password: str = secrets.token_urlsafe(6)
