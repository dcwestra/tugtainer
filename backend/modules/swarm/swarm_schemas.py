from datetime import datetime

from pydantic import BaseModel

from backend.modules.hosts.hosts_schemas import HostInfo


class SwarmClusterInfo(BaseModel):
    cluster_id: str
    cluster_name: str
    hosts: list[HostInfo]
    available_updates_count: int = 0


class SwarmServiceListItem(BaseModel):
    name: str
    service_id: str
    image: str | None = None
    replicas: int | None = None
    running_replicas: int | None = None
    mode: str = "replicated"
    update_status: str | None = None
    # DB-tracked fields (None if service not yet in DB)
    id: int | None = None
    check_enabled: bool | None = None
    update_enabled: bool | None = None
    update_available: bool | None = None
    checked_at: datetime | None = None
    updated_at: datetime | None = None


class SwarmServicePatchBody(BaseModel):
    check_enabled: bool | None = None
    update_enabled: bool | None = None
