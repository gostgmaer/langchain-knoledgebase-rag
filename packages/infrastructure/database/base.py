from sqlalchemy.orm import DeclarativeBase

from .metadata import metadata


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    metadata = metadata