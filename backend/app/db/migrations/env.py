"""Alembic migration environment.

NOTE: this app has two DBs (app + geo). Run migrations per-target with
`alembic -x target=app upgrade head` / `alembic -x target=geo upgrade head`,
or split into two Alembic configs (backend/alembic_app.ini, backend/alembic_geo.ini)
once the schemas stabilize. Placeholder wiring below defaults to the app DB.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db import models  # noqa: F401 - ensures models are registered on the Base metadata
from app.db.base import AppBase, GeoBase

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
target = context.get_x_argument(as_dictionary=True).get("target", "app")

if target == "geo":
    config.set_main_option("sqlalchemy.url", settings.geo_db_url)
    target_metadata = GeoBase.metadata
else:
    config.set_main_option("sqlalchemy.url", settings.app_db_url)
    target_metadata = AppBase.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
