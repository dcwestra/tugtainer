
from pydantic import BaseModel, ConfigDict

from backend.enums.host_type_enum import EHostType


class HostBase(BaseModel):
    name: str
    enabled: bool
    prune: bool
    prune_all: bool
    url: str
    secret: str | None = None
    ssl: bool
    timeout: int
    container_hc_timeout: int
    host_type: EHostType = EHostType.STANDALONE
    swarm_cluster_name: str | None = None


class HostInfo(HostBase):
    id: int
    available_updates_count: int = 0
    swarm_cluster_id: str | None = None
    model_config = ConfigDict(from_attributes=True)


class HostStatusResponseBody(BaseModel):
    id: int
    ok: bool | None = None
    err: str | None = None


class HostSummary(BaseModel):
    host_id: int
    host_name: str
    total_containers: int
    by_status: dict[str, int]
    by_health: dict[str, int]
    by_protected: dict[str, int]
    by_check_enabled: dict[str, int]
    by_update_enabled: dict[str, int]
    by_update_available: dict[str, int]
