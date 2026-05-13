from fastapi import APIRouter, Depends, HTTPException, status
from python_on_whales import DockerException

from swarm_agent.auth import verify_signature
from swarm_agent.config import Config
from swarm_agent.docker_client import DOCKER
from swarm_agent.unil.asyncall import asyncall
from shared.schemas.service_schemas import SwarmInfoSchema

router = APIRouter(
    prefix="/swarm",
    tags=["swarm"],
    dependencies=[Depends(verify_signature)],
)


@router.get(
    "/info",
    description="Get swarm cluster identity and node info",
    response_model=SwarmInfoSchema,
)
async def swarm_info() -> SwarmInfoSchema:
    try:
        info = await asyncall(DOCKER.info)
    except DockerException as e:
        raise HTTPException(
            status.HTTP_424_FAILED_DEPENDENCY,
            f"Failed to get swarm info: {e}",
        ) from e

    if info.swarm.local_node_state != "active":
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Docker is not in swarm mode",
        )

    return SwarmInfoSchema(
        cluster_id=(info.swarm.cluster.id or "") if info.swarm.cluster else "",
        cluster_label=Config.SWARM_CLUSTER_LABEL,
        node_id=info.swarm.node_id,
        is_manager=info.swarm.control_available,
    )
