from fastapi import APIRouter, Depends

from swarm_agent.auth import verify_signature
from swarm_agent.docker_client import DOCKER
from swarm_agent.unil.asyncall import asyncall
from shared.schemas.image_schemas import PruneImagesRequestBodySchema

router = APIRouter(
    prefix="/image",
    tags=["image"],
    dependencies=[Depends(verify_signature)],
)


@router.post(
    "/prune",
    description="Prune unused images on the swarm manager node",
)
async def prune(body: PruneImagesRequestBodySchema) -> str:
    args = body.model_dump(exclude_unset=True)
    return await asyncall(
        lambda: DOCKER.image.prune(**args),
        asyncall_timeout=600,
    )
