from fastapi import APIRouter, Depends, HTTPException, status

from agent.auth import verify_signature
from agent.docker_client import DOCKER
from agent.unil.asyncall import asyncall
from shared.schemas.docker_version_scheme import DockerVersionScheme
from shared.schemas.service_schemas import SwarmInfoSchema

router = APIRouter(
    prefix="/common",
    tags=["common"],
    dependencies=[Depends(verify_signature)],
)


@router.get(
    "/version",
    description="Get docker version",
    response_model=DockerVersionScheme,
)
async def get_version():
    return await asyncall(lambda: DOCKER.version())


@router.get(
    "/swarm_info",
    description="Get swarm cluster identity if this node is a swarm manager. Returns 404 if not in swarm mode.",
    response_model=SwarmInfoSchema,
)
async def swarm_info() -> SwarmInfoSchema:
    info = await asyncall(DOCKER.info)
    if info.swarm.local_node_state != "active" or not info.swarm.control_available:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not a swarm manager")
    return SwarmInfoSchema(
        cluster_id=(info.swarm.cluster.id or "") if info.swarm.cluster else "",
        cluster_label=None,
        node_id=info.swarm.node_id,
        is_manager=True,
    )
