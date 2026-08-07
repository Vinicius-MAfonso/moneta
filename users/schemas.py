import uuid
from ninja import Schema


class UserProfileOut(Schema):
    id: uuid.UUID
    username: str
    email: str
    first_name: str
    last_name: str
    photo_url: str | None = None
    currency: str
    timezone: str


class UserProfileUpdateIn(Schema):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    photo_url: str | None = None
    currency: str | None = None
    timezone: str | None = None
