import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.agent_client import AgentClientManager
from backend.core.check_actions.check_swarm_services import (
    check_swarm_cluster,
    check_swarm_service,
)
from backend.core.update_actions.update_swarm_services import (
    update_swarm_cluster,
    update_swarm_service,
)
from backend.db.session import get_async_session
from backend.modules.auth.auth_util import is_authorized
from backend.modules.hosts.hosts_model import HostsModel
from backend.modules.hosts.hosts_schemas import HostInfo
from backend.modules.swarm.swarm_model import SwarmServicesModel
from backend.modules.swarm.swarm_schemas import (
    SwarmClusterInfo,
    SwarmServiceListItem,
    SwarmServicePatchBody,
)
from backend.core.progress.progress_util import (
    get_swarm_cluster_cache_key,
    get_swarm_service_cache_key,
)
from backend.modules.swarm.swarm_util import (
    display_cluster_name,
    get_cluster_hosts,
    get_online_swarm_client,
    get_or_create_service_db,
    map_service_schema,
)

swarm_router = APIRouter(
    prefix="/swarm",
    tags=["swarm"],
    dependencies=[Depends(is_authorized)],
)

logger = logging.getLogger(__name__)


@swarm_router.get(
    "/clusters",
    response_model=list[SwarmClusterInfo],
    description="List all registered swarm clusters (grouped by cluster ID)",
)
async def list_clusters(
    session: AsyncSession = Depends(get_async_session),
) -> list[SwarmClusterInfo]:
    stmt = select(HostsModel).where(HostsModel.swarm_cluster_id.isnot(None))
    result = await session.execute(stmt)
    hosts = list(result.scalars().all())

    # Group by cluster_id
    clusters: dict[str, list[HostsModel]] = {}
    for h in hosts:
        clusters.setdefault(h.swarm_cluster_id, []).append(h)

    # Count available updates per cluster
    update_counts: dict[str, int] = {}
    if hosts:
        all_cluster_ids = list(clusters.keys())
        svc_stmt = select(
            SwarmServicesModel.swarm_cluster_id,
        ).where(
            SwarmServicesModel.swarm_cluster_id.in_(all_cluster_ids),
            SwarmServicesModel.update_available.is_(True),
        )
        svc_result = await session.execute(svc_stmt)
        for (cid,) in svc_result.all():
            update_counts[cid] = update_counts.get(cid, 0) + 1

    return [
        SwarmClusterInfo(
            cluster_id=cid,
            cluster_name=display_cluster_name(cluster_hosts[0]),
            hosts=[HostInfo.model_validate(h) for h in cluster_hosts],
            available_updates_count=update_counts.get(cid, 0),
        )
        for cid, cluster_hosts in clusters.items()
    ]


@swarm_router.get(
    "/{cluster_id}/services",
    response_model=list[SwarmServiceListItem],
    description="List services in a swarm cluster",
)
async def list_services(
    cluster_id: str,
    session: AsyncSession = Depends(get_async_session),
) -> list[SwarmServiceListItem]:
    client = await get_online_swarm_client(cluster_id, session)
    if not client:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No reachable swarm agent found for this cluster",
        )

    raw_services = await client.service.list()

    db_stmt = select(SwarmServicesModel).where(
        SwarmServicesModel.swarm_cluster_id == cluster_id
    )
    db_result = await session.execute(db_stmt)
    db_map = {item.name: item for item in db_result.scalars().all()}

    return [
        map_service_schema(
            svc,
            db_map.get(svc.get("Spec", {}).get("Name", "")),
        )
        for svc in raw_services
    ]


@swarm_router.patch(
    "/{cluster_id}/services/{service_name}",
    response_model=SwarmServiceListItem,
    description="Update check/update settings for a swarm service",
)
async def patch_service(
    cluster_id: str,
    service_name: str,
    body: SwarmServicePatchBody,
    session: AsyncSession = Depends(get_async_session),
) -> SwarmServiceListItem:
    client = await get_online_swarm_client(cluster_id, session)
    if not client:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No reachable swarm agent found for this cluster",
        )

    db_item = await get_or_create_service_db(session, cluster_id, service_name)
    if body.check_enabled is not None:
        db_item.check_enabled = body.check_enabled
    if body.update_enabled is not None:
        db_item.update_enabled = body.update_enabled
    await session.commit()
    await session.refresh(db_item)

    try:
        raw = await client.service.inspect(service_name)
    except Exception:
        raw = {"Spec": {"Name": service_name}, "ID": service_name}

    return map_service_schema(raw, db_item)


@swarm_router.put(
    "/{cluster_id}/name",
    response_model=list[HostInfo],
    description="Set a display name for a swarm cluster (applied to all its agents)",
)
async def set_cluster_name(
    cluster_id: str,
    name: str,
    session: AsyncSession = Depends(get_async_session),
) -> list[HostInfo]:
    hosts = await get_cluster_hosts(cluster_id, session)
    if not hosts:
        raise HTTPException(404, "Swarm cluster not found")
    for host in hosts:
        host.swarm_cluster_name = name
    await session.commit()
    return [HostInfo.model_validate(h) for h in hosts]


@swarm_router.get(
    "/{cluster_id}/services/{service_name}/logs",
    description="Get aggregated logs for a swarm service",
)
async def service_logs(
    cluster_id: str,
    service_name: str,
    tail: int = 100,
    timestamps: bool = False,
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    client = await get_online_swarm_client(cluster_id, session)
    if not client:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No reachable swarm agent found for this cluster",
        )
    logs = await client.service.logs(service_name, tail=tail, timestamps=timestamps)
    return Response(content=logs, media_type="text/plain")


@swarm_router.get(
    "/{cluster_id}/status",
    description="Check reachability of swarm agents in a cluster",
)
async def cluster_status(
    cluster_id: str,
    session: AsyncSession = Depends(get_async_session),
):
    hosts = await get_cluster_hosts(cluster_id, session)
    if not hosts:
        raise HTTPException(404, "Swarm cluster not found")

    results = []
    for host in hosts:
        try:
            client = AgentClientManager.get_swarm_client(host)
            await client.public.health()
            await client.public.access()
            results.append({"id": host.id, "name": host.name, "ok": True})
        except Exception as e:
            results.append({"id": host.id, "name": host.name, "ok": False, "err": str(e)})

    return results


@swarm_router.post(
    "/{cluster_id}/services/{service_name}/check",
    response_model=str,
    description="Trigger a manual check for image update on a single service. Returns cache_id for progress polling.",
)
async def check_single_service(
    cluster_id: str,
    service_name: str,
    session: AsyncSession = Depends(get_async_session),
) -> str:
    client = await get_online_swarm_client(cluster_id, session)
    if not client:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No reachable swarm agent found for this cluster",
        )
    asyncio.create_task(check_swarm_service(cluster_id, service_name, client))
    return get_swarm_service_cache_key(cluster_id, service_name)


@swarm_router.post(
    "/{cluster_id}/services/{service_name}/update",
    response_model=str,
    description="Trigger an update for a single swarm service. Returns cache_id for progress polling.",
)
async def update_single_service(
    cluster_id: str,
    service_name: str,
    session: AsyncSession = Depends(get_async_session),
) -> str:
    client = await get_online_swarm_client(cluster_id, session)
    if not client:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No reachable swarm agent found for this cluster",
        )
    hosts = await get_cluster_hosts(cluster_id, session)
    first_host = hosts[0] if hosts else None
    asyncio.create_task(update_swarm_service(cluster_id, service_name, client, first_host))
    return get_swarm_service_cache_key(cluster_id, service_name)


@swarm_router.post(
    "/{cluster_id}/services/check",
    response_model=str,
    description="Trigger a manual check for all services in a cluster. Returns cache_id for progress polling.",
)
async def check_cluster_services(
    cluster_id: str,
    session: AsyncSession = Depends(get_async_session),
) -> str:
    client = await get_online_swarm_client(cluster_id, session)
    if not client:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No reachable swarm agent found for this cluster",
        )
    hosts = await get_cluster_hosts(cluster_id, session)
    cluster_name = display_cluster_name(hosts[0]) if hosts else cluster_id
    asyncio.create_task(check_swarm_cluster(cluster_id, cluster_name, client, True))
    return get_swarm_cluster_cache_key(cluster_id)


@swarm_router.post(
    "/{cluster_id}/services/update",
    response_model=str,
    description="Trigger a manual update for all services with update_available=True in a cluster. Returns cache_id for progress polling.",
)
async def update_cluster_services(
    cluster_id: str,
    session: AsyncSession = Depends(get_async_session),
) -> str:
    client = await get_online_swarm_client(cluster_id, session)
    if not client:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No reachable swarm agent found for this cluster",
        )
    hosts = await get_cluster_hosts(cluster_id, session)
    first_host = hosts[0] if hosts else None
    cluster_name = display_cluster_name(first_host) if first_host else cluster_id
    asyncio.create_task(update_swarm_cluster(cluster_id, cluster_name, client, first_host))
    return get_swarm_cluster_cache_key(cluster_id)
