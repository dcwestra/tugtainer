import logging

from fastapi import APIRouter, Depends, HTTPException, status
from python_on_whales import DockerException

from swarm_agent.auth import verify_signature
from swarm_agent.docker_client import DOCKER
from swarm_agent.unil.asyncall import asyncall

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/health", description="Get health status of the swarm agent")
async def health():
    try:
        info = await asyncall(DOCKER.info)
    except DockerException as e:
        message = "Failed to get docker info"
        logging.exception(message)
        raise HTTPException(status.HTTP_424_FAILED_DEPENDENCY, message) from e

    if info.swarm.local_node_state != "active":
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Docker is not in swarm mode on this node",
        )
    if not info.swarm.control_available:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "This node is not a swarm manager — swarm agent must run on a manager node",
        )
    return "OK"


@router.get(
    "/access",
    description="Signature verification — raises exception on falsy signature",
)
async def access(_=Depends(verify_signature)):
    return "OK"
