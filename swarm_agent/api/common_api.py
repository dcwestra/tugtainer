from fastapi import APIRouter, Depends

from swarm_agent.auth import verify_signature
from swarm_agent.docker_client import DOCKER
from swarm_agent.unil.asyncall import asyncall
from shared.schemas.docker_version_scheme import DockerVersionScheme

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
