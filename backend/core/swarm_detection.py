import logging

from sqlalchemy import select

from backend.db.session import async_session_maker
from backend.enums.host_type_enum import EHostType
from backend.modules.hosts.hosts_model import HostsModel

logger = logging.getLogger(__name__)


async def detect_local_swarm_clusters() -> None:
    """
    On startup, check all enabled standalone hosts to see if their Docker daemon
    is a swarm manager. If so, record the cluster_id on the host so the swarm
    check/update flows and the UI can surface the cluster automatically.

    Errors are logged as warnings — the local agent may not yet be ready.
    """
    from backend.core.agent_client import AgentClientManager

    async with async_session_maker() as session:
        stmt = select(HostsModel).where(
            HostsModel.enabled.is_(True),
            HostsModel.host_type == EHostType.STANDALONE,
        )
        hosts = list((await session.execute(stmt)).scalars().all())

    for host in hosts:
        try:
            client = AgentClientManager.get_host_client(host)
            info = await client.common.swarm_info()
        except Exception:
            logger.warning(
                f"Could not check swarm status of host {host.id}.{host.name} — "
                "agent may not be ready yet"
            )
            continue

        if not info or not info.is_manager:
            continue

        if host.swarm_cluster_id == info.cluster_id:
            # Already detected and recorded — nothing to do
            continue

        # Check for duplicate cluster registration among other hosts
        async with async_session_maker() as session:
            dup_stmt = (
                select(HostsModel)
                .where(
                    HostsModel.swarm_cluster_id == info.cluster_id,
                    HostsModel.id != host.id,
                )
                .limit(1)
            )
            duplicate = (await session.execute(dup_stmt)).scalar_one_or_none()

        if duplicate:
            logger.warning(
                f"Host {host.id}.{host.name} is a swarm manager for cluster "
                f"'{info.cluster_id}', but that cluster is already registered "
                f"via host '{duplicate.name}'. Skipping auto-detection."
            )
            continue

        logger.info(
            f"Auto-detected swarm cluster '{info.cluster_id}' on host "
            f"{host.id}.{host.name} — recording cluster_id"
        )

        async with async_session_maker() as session:
            db_host = await session.get(HostsModel, host.id)
            if not db_host:
                continue
            db_host.swarm_cluster_id = info.cluster_id
            if info.cluster_label and not db_host.swarm_cluster_name:
                db_host.swarm_cluster_name = info.cluster_label
            await session.commit()
            await session.refresh(db_host)

        # Recreate the client as SwarmAgentClient now that cluster_id is set
        try:
            async with async_session_maker() as session:
                refreshed = await session.get(HostsModel, host.id)
            if refreshed:
                await AgentClientManager.set_client(refreshed)
        except Exception:
            logger.warning(
                f"Failed to upgrade client for host {host.id}.{host.name} "
                "to SwarmAgentClient after detection"
            )
