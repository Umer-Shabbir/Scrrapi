"""Geo reference schema, seeded from GeoNames `allCountries.txt`.
Lives in the separate geo DB (GeoBase), mirroring the legacy country/region/city/zip split."""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import GeoBase


class Country(GeoBase):
    __tablename__ = "country"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(2), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)


class Region(GeoBase):
    __tablename__ = "region"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    country_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("country.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)


class City(GeoBase):
    __tablename__ = "city"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    region_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("region.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)


class ZipCode(GeoBase):
    __tablename__ = "zip_code"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    city_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("city.id"), index=True)
    code: Mapped[str] = mapped_column(String(20), index=True)
