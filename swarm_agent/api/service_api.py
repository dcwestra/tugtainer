from fastapi import APIRouter, Depends, HTTPException, status
from python_on_whales.components.service.models import ServiceInspectResult

from swarm_agent.auth import verify_signature
from swarm_agent.docker_client import DOCKER
from swarm_agent.unil.asyncall import asyncall
from shared.schemas.service_schemas import ServiceUpdateRequestBody

router = APIRouter(
    prefix="/service",
    tags=["service"],
    dependencies=[Depends(verify_signature)],
)


@router.get(
    "/list",
    description="Get list of all swarm services",
    response_model=list[ServiceInspectResult],  # type: ignore
)
async def list_services():
    return await asyncall(lambda: DOCKER.service.list())


@router.get(
    "/inspect/{name_or_id}",
    description="Inspect a swarm service",
    response_model=ServiceInspectResult,  # type: ignore
)
async def inspect_service(name_or_id: str):
    try:
        return await asyncall(lambda: DOCKER.service.inspect(name_or_id))
    except Exception as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Service not found: {e}") from e


@router.post(
    "/update",
    description="Update a swarm service to a new image (detached — Swarm orchestrates the rollout)",
    response_model=str,
)
async def update_service(body: ServiceUpdateRequestBody) -> str:
    try:
        await asyncall(
            lambda: DOCKER.service.update(body.service_id, image=body.image, detach=True),
            asyncall_timeout=60,
        )
        return body.service_id
    except Exception as e:
        raise HTTPException(
            status.HTTP_424_FAILED_DEPENDENCY,
            f"Failed to update service: {e}",
        ) from e


@router.get(
    "/logs/{name_or_id}",
    description="Get recent logs of a swarm service (aggregated across all tasks)",
    response_model=str,
)
async def service_logs(name_or_id: str, tail: int = 100) -> str:
    try:
        result = await asyncall(
            lambda: DOCKER.service.logs(name_or_id, tail=tail),
            asyncall_timeout=60,
        )
        return str(result) if result else ""
    except Exception as e:
        raise HTTPException(
            status.HTTP_424_FAILED_DEPENDENCY,
            f"Failed to get service logs: {e}",
        ) from e
