import json

from fastapi import APIRouter, Depends, HTTPException, status

from agent.auth import verify_signature
from agent.docker_client import DOCKER
from agent.unil.asyncall import asyncall
from shared.schemas.service_schemas import ServiceUpdateRequestBody

router = APIRouter(
    prefix="/service",
    tags=["service"],
    dependencies=[Depends(verify_signature)],
)


async def _require_swarm_manager():
    info = await asyncall(DOCKER.info)
    if not info.swarm.control_available:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Docker is not in swarm manager mode",
        )


@router.get(
    "/list",
    description="Get list of all swarm services with running task counts",
)
async def list_services():
    await _require_swarm_manager()

    def _get_services_and_tasks() -> list[dict]:
        from python_on_whales.utils import run

        services = DOCKER.service.list()
        if not services:
            return []

        ids = [s.id for s in services]

        # Batch inspect for full service JSON — includes ServiceStatus with task counts
        raw_list: list[dict] = json.loads(
            run(DOCKER.docker_cmd + ["service", "inspect"] + ids)
        )

        # ServiceStatus.RunningTasks / DesiredTasks are present in Docker 23+
        # and available directly in the inspect output — no extra ps call needed
        for svc in raw_list:
            ss = svc.get("ServiceStatus") or {}
            svc["RunningTasks"] = ss.get("RunningTasks", 0)
            svc["DesiredTasks"] = ss.get("DesiredTasks")

        return raw_list

    return await asyncall(_get_services_and_tasks)


@router.get(
    "/inspect/{name_or_id}",
    description="Inspect a swarm service",
)
async def inspect_service(name_or_id: str):
    await _require_swarm_manager()
    try:
        return await asyncall(lambda: DOCKER.service.inspect(name_or_id))
    except Exception as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Service not found: {e}") from e


@router.post(
    "/update",
    description="Update a swarm service to a new image (detached rolling update)",
    response_model=str,
)
async def update_service(body: ServiceUpdateRequestBody) -> str:
    await _require_swarm_manager()
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
async def service_logs(
    name_or_id: str,
    tail: int = 100,
    timestamps: bool = False,
) -> str:
    await _require_swarm_manager()
    try:
        result = await asyncall(
            lambda: DOCKER.service.logs(name_or_id, tail=tail, timestamps=timestamps),
            asyncall_timeout=60,
        )
        return str(result) if result else ""
    except Exception as e:
        raise HTTPException(
            status.HTTP_424_FAILED_DEPENDENCY,
            f"Failed to get service logs: {e}",
        ) from e
