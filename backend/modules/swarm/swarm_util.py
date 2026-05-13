import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.agent_client import AgentClientManager, SwarmAgentClient
from backend.modules.hosts.hosts_model import HostsModel
from backend.modules.swarm.swarm_model import SwarmServicesModel
from backend.modules.swarm.swarm_schemas import SwarmServiceListItem


def _extract_service_image(svc: dict) -> str | None:
    """Pull the image spec out of a raw service inspect dict."""
    try:
        return svc["Spec"]["TaskTemplate"]["ContainerSpec"]["Image"]
    except (KeyError, TypeError):
        return None


def _extract_service_mode(svc: dict) -> tuple[str, int | None]:
    """Return (mode_name, desired_replicas) from a raw service inspect dict."""
    try:
        mode = svc["Spec"]["Mode"]
        if "Replicated" in mode:
            return "replicated", mode["Replicated"].get("Replicas")
        if "Global" in mode:
            # For global services use DesiredTasks (one per eligible node)
            desired = svc.get("DesiredTasks")
            return "global", desired
    except (KeyError, TypeError):
        pass
    return "replicated", None


def _extract_update_status(svc: dict) -> str | None:
    try:
        return svc["UpdateStatus"]["State"]
    except (KeyError, TypeError):
        return None


def map_service_schema(
    svc: dict,
    db_item: SwarmServicesModel | None,
) -> SwarmServiceListItem:
    mode, replicas = _extract_service_mode(svc)
    running_replicas: int | None = svc.get("RunningTasks")
    return SwarmServiceListItem(
        name=svc.get("Spec", {}).get("Name", svc.get("ID", "")),
        service_id=svc.get("ID", ""),
        image=_extract_service_image(svc),
        replicas=replicas,
        running_replicas=running_replicas,
        mode=mode,
        update_status=_extract_update_status(svc),
        id=db_item.id if db_item else None,
        check_enabled=db_item.check_enabled if db_item else None,
        update_enabled=db_item.update_enabled if db_item else None,
        update_available=db_item.update_available if db_item else None,
        checked_at=db_item.checked_at if db_item else None,
        updated_at=db_item.updated_at if db_item else None,
    )


async def get_cluster_hosts(
    cluster_id: str, session: AsyncSession
) -> list[HostsModel]:
    """Return all enabled swarm agent hosts for a given cluster_id."""
    stmt = select(HostsModel).where(
        HostsModel.swarm_cluster_id == cluster_id,
        HostsModel.enabled.is_(True),
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_online_swarm_client(
    cluster_id: str, session: AsyncSession
) -> SwarmAgentClient | None:
    """Return the first reachable swarm client for the cluster, or None."""
    hosts = await get_cluster_hosts(cluster_id, session)
    for host in hosts:
        try:
            client = AgentClientManager.get_swarm_client(host)
            await client.public.health()
            return client
        except Exception:
            logging.warning(
                f"Swarm agent {host.id}.{host.name} unreachable, trying next"
            )
    return None


async def get_or_create_service_db(
    session: AsyncSession,
    cluster_id: str,
    service_name: str,
) -> SwarmServicesModel:
    stmt = (
        select(SwarmServicesModel)
        .where(
            SwarmServicesModel.swarm_cluster_id == cluster_id,
            SwarmServicesModel.name == service_name,
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    db_item = result.scalar_one_or_none()
    if not db_item:
        db_item = SwarmServicesModel(
            swarm_cluster_id=cluster_id,
            name=service_name,
        )
        session.add(db_item)
        await session.flush()
    return db_item


def display_cluster_name(host: HostsModel) -> str:
    """Return the best display name for a swarm cluster from a representative host."""
    if host.swarm_cluster_name:
        return host.swarm_cluster_name
    if host.swarm_cluster_id:
        return f"swarm-{host.swarm_cluster_id[:8]}"
    return host.name
