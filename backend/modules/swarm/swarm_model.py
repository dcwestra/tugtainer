from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base_model import BaseModel
from backend.util.now import now


class SwarmServicesModel(BaseModel):
    """Tracks update state for Docker Swarm services."""

    __tablename__ = "swarm_services"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    swarm_cluster_id: Mapped[str] = mapped_column(
        String, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(
        String, nullable=False, index=True
    )
    check_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("FALSE")
    )
    update_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("FALSE")
    )
    update_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("FALSE")
    )
    checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        default=now,
        nullable=False,
    )
    modified_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
        onupdate=now,
        default=now,
        nullable=False,
    )
    image_id: Mapped[str | None] = mapped_column(String, nullable=True)
    local_digests: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    remote_digests: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
