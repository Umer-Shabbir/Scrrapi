from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AppBase


class AppSetting(AppBase):
    """One runtime-editable preference, keyed by name.

    Deliberately a key/value table rather than a column per setting: these are
    read by the API *and* by every worker process, so they have to live
    somewhere shared, and they change from the UI rather than from a deploy.
    Anything that belongs to the deployment instead (database URLs, time limits,
    proxy mode) stays in `app.core.config.Settings`, which is environment-only.

    Values are stored as text and parsed by the accessor in
    `app.core.runtime_settings`, which is also where the validation lives -- a
    row written by hand with nonsense in it falls back to the configured
    default rather than breaking the dispatcher.
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
