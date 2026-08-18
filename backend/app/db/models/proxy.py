import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AppBase

PROXY_STATUSES = ("active", "disabled", "retired", "cooling")


class Proxy(AppBase):
    """One entry in the DB-backed proxy pool (Proxies screen).

    Backs `app.scraping.proxy.pool.ProxyPool`'s "list" mode -- "single"/"free"
    modes are unaffected. See PROXY_STATUSES and the migration docstring for
    what each status means; success_rate/avg_latency_ms are computed
    properties rather than stored columns since they're pure functions of the
    running counters below.
    """

    __tablename__ = "proxies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer)
    protocol: Mapped[str] = mapped_column(String(10), default="http")
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Free-text label, not derived from a geo lookup -- there is no IP
    # geolocation service in this codebase. Set by whoever adds the proxy.
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="active")

    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    block_count: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms_total: Mapped[int] = mapped_column(BigInteger, default=0)
    latency_samples: Mapped[int] = mapped_column(Integer, default=0)

    cooling_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @property
    def total_uses(self) -> int:
        return self.success_count + self.failure_count + self.block_count

    @property
    def success_rate(self) -> float | None:
        """0-100, or None if this proxy has never been used -- distinct from
        a real 0% success rate, which is worth showing differently."""
        if self.total_uses == 0:
            return None
        return round(100 * self.success_count / self.total_uses, 1)

    @property
    def block_rate(self) -> float | None:
        if self.total_uses == 0:
            return None
        return round(100 * self.block_count / self.total_uses, 1)

    @property
    def avg_latency_ms(self) -> int | None:
        if self.latency_samples == 0:
            return None
        return round(self.latency_ms_total / self.latency_samples)

    def url(self) -> str:
        """Reconstructs the proxy URL ProxyPool.get_proxy() would hand a
        scraper -- `scheme://user:pass@host:port` with credentials omitted
        when absent."""
        auth = f"{self.username}:{self.password}@" if self.username else ""
        return f"{self.protocol}://{auth}{self.host}:{self.port}"
