from pydantic import BaseModel


class ServiceUpdateRequestBody(BaseModel):
    service_id: str
    image: str


class SwarmInfoSchema(BaseModel):
    cluster_id: str
    cluster_label: str | None = None
    node_id: str
    is_manager: bool
