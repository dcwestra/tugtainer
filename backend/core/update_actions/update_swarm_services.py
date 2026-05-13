import logging
from typing import Final

from sqlalchemy import select

from backend.core.action_result import (
    SwarmClusterActionResult,
    SwarmServiceActionResult,
)
from backend.core.agent_client import SwarmAgentClient
from backend.core.progress.progress_cache import ProgressCache
from backend.core.progress.progress_schemas import (
    AllSwarmActionProgress,
    SwarmClusterActionProgress,
)
from backend.core.progress.progress_util import (
    ALL_SWARM_CLUSTERS_STATUS_KEY,
    get_swarm_cluster_cache_key,
    get_swarm_service_cache_key,
    is_allowed_start_cache,
)
from backend.db.session import async_session_maker
from backend.enums.action_status_enum import EActionStatus
from backend.modules.hosts.hosts_model import HostsModel
from backend.modules.swarm.swarm_model import SwarmServicesModel
from backend.modules.swarm.swarm_util import display_cluster_name, get_cluster_hosts, get_or_create_service_db
from backend.util.now import now
from shared.schemas.image_schemas import PruneImagesRequestBodySchema
from shared.schemas.service_schemas import ServiceUpdateRequestBody


async def update_swarm_cluster(
    cluster_id: str,
    cluster_name: str,
    client: SwarmAgentClient,
    host: HostsModel | None = None,
) -> SwarmClusterActionResult:
    """
    Update all services in a swarm cluster that have update_available=True
    and update_enabled=True.
    """
    result: Final = SwarmClusterActionResult(
        cluster_id=cluster_id, cluster_name=cluster_name
    )
    cache_key: Final = get_swarm_cluster_cache_key(cluster_id)
    cache: Final = ProgressCache[SwarmClusterActionProgress](cache_key)
    state: Final = cache.get()
    logger: Final = logging.getLogger(f"update_swarm_cluster.{cluster_id[:8]}")

    if not is_allowed_start_cache(state):
        logger.warning("Update action already running. Exiting.")
        return result

    try:
        logger.info("Starting swarm cluster update")
        cache.set({"status": EActionStatus.PREPARING})

        async with async_session_maker() as session:
            stmt = select(SwarmServicesModel).where(
                SwarmServicesModel.swarm_cluster_id == cluster_id,
                SwarmServicesModel.update_available.is_(True),
                SwarmServicesModel.update_enabled.is_(True),
            )
            db_rows = (await session.execute(stmt)).scalars().all()

        if not db_rows:
            logger.info("No services to update")
            cache.update({"status": EActionStatus.DONE, "result": result})
            return result

        cache.update({"status": EActionStatus.UPDATING})

        # Get live services to find current image+id for each
        raw_services = await client.service.list()
        raw_by_name: dict[str, dict] = {}
        for svc in raw_services:
            name = svc.get("Spec", {}).get("Name", "")
            if name:
                raw_by_name[name] = svc

        for db_row in db_rows:
            svc_result = SwarmServiceActionResult(
                service_name=db_row.name,
                service_id=db_row.name,
            )

            raw = raw_by_name.get(db_row.name)
            if not raw:
                logger.warning(f"Service {db_row.name} not found in live list, skipping")
                svc_result.result = "failed"
                result.items.append(svc_result)
                continue

            service_id: str = raw.get("ID", db_row.name)
            svc_result.service_id = service_id

            image_raw: str = (
                raw.get("Spec", {})
                .get("TaskTemplate", {})
                .get("ContainerSpec", {})
                .get("Image", "")
            )
            if not image_raw:
                logger.warning(f"No image spec for {db_row.name}, skipping")
                svc_result.result = "failed"
                result.items.append(svc_result)
                continue

            # Strip the digest — docker service update with a plain spec triggers pull
            base_image = image_raw.split("@")[0] if "@" in image_raw else image_raw
            svc_result.image_spec = base_image

            try:
                logger.info(f"Updating service {db_row.name} to {base_image}")
                await client.service.update(
                    ServiceUpdateRequestBody(service_id=service_id, image=base_image)
                )
                svc_result.result = "updated"
                logger.info(f"Service {db_row.name} update triggered")

                async with async_session_maker() as session:
                    stmt2 = (
                        select(SwarmServicesModel)
                        .where(
                            SwarmServicesModel.swarm_cluster_id == cluster_id,
                            SwarmServicesModel.name == db_row.name,
                        )
                        .limit(1)
                    )
                    db_item = (await session.execute(stmt2)).scalar_one_or_none()
                    if db_item:
                        db_item.updated_at = now()
                        db_item.update_available = False
                        await session.commit()

            except Exception:
                logger.exception(f"Failed to update service {db_row.name}")
                svc_result.result = "failed"

            result.items.append(svc_result)

        if host and host.prune and result.items:
            cache.update({"status": EActionStatus.PRUNING})
            logger.info("Pruning images on swarm manager node...")
            try:
                result.prune_result = await client.image.prune(
                    PruneImagesRequestBodySchema(all=host.prune_all)
                )
            except Exception:
                logger.exception("Failed to prune images on swarm manager")

        cache.update({"status": EActionStatus.DONE, "result": result})
        return result

    except Exception:
        logger.exception(f"Failed to update swarm cluster {cluster_id}")
        cache.update({"status": EActionStatus.ERROR})
        return result


async def update_swarm_service(
    cluster_id: str,
    service_name: str,
    client: SwarmAgentClient,
    host: HostsModel | None = None,
) -> None:
    """Update a single swarm service by name."""
    logger = logging.getLogger(f"update_swarm_service.{cluster_id[:8]}.{service_name}")
    cache_key: Final = get_swarm_service_cache_key(cluster_id, service_name)
    cache: Final = ProgressCache[SwarmClusterActionProgress](cache_key)

    if not is_allowed_start_cache(cache.get()):
        logger.warning(f"Update for {service_name} already running. Exiting.")
        return

    cache.set({"status": EActionStatus.UPDATING})

    try:
        raw_services = await client.service.list()
        raw_by_name: dict[str, dict] = {
            svc.get("Spec", {}).get("Name", ""): svc
            for svc in raw_services
            if svc.get("Spec", {}).get("Name", "")
        }

        raw = raw_by_name.get(service_name)
        if not raw:
            logger.warning(f"Service {service_name} not found in live list")
            return

        service_id: str = raw.get("ID", service_name)
        image_raw: str = (
            raw.get("Spec", {})
            .get("TaskTemplate", {})
            .get("ContainerSpec", {})
            .get("Image", "")
        )
        if not image_raw:
            logger.warning(f"No image spec for {service_name}")
            return

        base_image = image_raw.split("@")[0] if "@" in image_raw else image_raw
        logger.info(f"Updating service {service_name} to {base_image}")
        await client.service.update(
            ServiceUpdateRequestBody(service_id=service_id, image=base_image)
        )

        async with async_session_maker() as session:
            db_item = await get_or_create_service_db(session, cluster_id, service_name)
            db_item.updated_at = now()
            db_item.update_available = False
            await session.commit()

        logger.info(f"Service {service_name} updated successfully")
        cache.update({"status": EActionStatus.DONE})

    except Exception:
        logger.exception(f"Failed to update service {service_name}")
        cache.update({"status": EActionStatus.ERROR})


async def update_all_swarm_clusters() -> list[SwarmClusterActionResult]:
    """
    Update all swarm clusters — services with update_available + update_enabled.
    """
    from backend.core.agent_client import AgentClientManager

    cache: Final = ProgressCache[AllSwarmActionProgress](ALL_SWARM_CLUSTERS_STATUS_KEY)
    state: Final = cache.get()
    logger: Final = logging.getLogger("update_all_swarm_clusters")

    if not is_allowed_start_cache(state):
        logger.warning("Swarm update already running. Exiting.")
        return []

    try:
        cache.set({"status": EActionStatus.PREPARING})
        logger.info("Starting swarm cluster updates")

        async with async_session_maker() as session:
            stmt = select(HostsModel).where(
                HostsModel.enabled.is_(True),
                HostsModel.swarm_cluster_id.isnot(None),
            )
            hosts = (await session.execute(stmt)).scalars().all()

        seen_clusters: set[str] = set()
        cluster_host_map: dict[str, HostsModel] = {}
        for h in hosts:
            cid = h.swarm_cluster_id
            if cid and cid not in seen_clusters:
                seen_clusters.add(cid)
                cluster_host_map[cid] = h

        cache.update({"status": EActionStatus.UPDATING})
        results: list[SwarmClusterActionResult] = []

        for cluster_id, host in cluster_host_map.items():
            async with async_session_maker() as session:
                cluster_hosts = await get_cluster_hosts(cluster_id, session)

            client = None
            for ch in cluster_hosts:
                try:
                    c = AgentClientManager.get_swarm_client(ch)
                    await c.public.health()
                    client = c
                    break
                except Exception:
                    logger.warning(f"Swarm host {ch.id}.{ch.name} unreachable")

            if not client:
                logger.warning(f"No reachable agent for cluster {cluster_id[:8]}, skipping")
                continue

            try:
                cluster_name = display_cluster_name(host)
                res = await update_swarm_cluster(cluster_id, cluster_name, client, host)
                results.append(res)
            except Exception:
                logger.exception(f"Failed to update swarm cluster {cluster_id}")

        cache.update(
            {
                "status": EActionStatus.DONE,
                "result": {r.cluster_id: r for r in results},
            }
        )
        return results

    except Exception:
        cache.update({"status": EActionStatus.ERROR})
        logger.exception("Error during swarm cluster updates")
        return []
