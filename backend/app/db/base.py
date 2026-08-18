"""Declarative bases. App DB and geo DB are separate schemas/instances,
so they get separate Base classes to keep Alembic migrations independent."""

from sqlalchemy.orm import DeclarativeBase


class AppBase(DeclarativeBase):
    pass


class GeoBase(DeclarativeBase):
    pass
