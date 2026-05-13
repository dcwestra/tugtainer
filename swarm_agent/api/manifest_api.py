from fastapi import APIRouter, Depends

from swarm_agent.auth import verify_signature
from swarm_agent.docker_client import DOCKER
from swarm_agent.unil.asyncall import asyncall
from shared.schemas.manifest_schema import ManifestInspectSchema

router = APIRouter(
    prefix="/manifest",
    tags=["manifest"],
    dependencies=[Depends(verify_signature)],
)


@router.get(
    path="/inspect",
    description="Inspect image manifest (used by backend for update checking)",
    response_model=ManifestInspectSchema,
)
async def imagetools_inspect(spec_or_digest: str):
    return await asyncall(
        lambda: DOCKER.manifest.inspect(spec_or_digest),
        asyncall_timeout=60,
    )
