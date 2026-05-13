import asyncio
import logging
from typing import Final

from sqlalchemy import select

from backend.core.action_result import (
    SwarmClusterActionResult,
    SwarmServiceActionResult,
    SwarmServiceCheckResultType,
)
from backend.core.agent_client import SwarmAgentClient
from backend.core.check_actions.check_actions_util import get_image_remote_digest
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
from backend.modules.settings.settings_enum import ESettingKey
from backend.modules.settings.settings_storage import SettingsStorage
from backend.modules.swarm.swarm_model import SwarmServicesModel
from backend.modules.swarm.swarm_util import (
    display_cluster_name,
    get_cluster_hosts,
    get_or_create_service_db,
)
from backend.util.jitter import jitter
from backend.util.now import now


def _split_image_spec(image: str) -> tuple[str, str | None]:
    """
    Split a Docker service image spec into (base_spec, local_digest).
    Docker annotates deployed images like: nginx:latest@sha256:abc123...
    """
    if "@" in image:
        base, digest = image.rsplit("@", 1)
        return base, digest
    return image, None


async def check_swarm_cluster(
    cluster_id: str,
    cluster_name: str,
    client: SwarmAgentClient,
    manual: bool = False,
) -> SwarmClusterActionResult:
    """
    Check all services in a swarm cluster for image updates.
    :param cluster_id: Docker cluster UUID
    :param cluster_name: display name for the cluster
    :param client: reachable SwarmAgentClient for this cluster
    :param manual: if True, check all services regardless of check_enabled
    """
    result: Final = SwarmClusterActionResult(
        cluster_id=cluster_id, cluster_name=cluster_name
    )
    cache_key: Final = get_swarm_cluster_cache_key(cluster_id)
    cache: Final = ProgressCache[SwarmClusterActionProgress](cache_key)
    state: Final = cache.get()
    logger: Final = logging.getLogger(f"check_swarm_cluster.{cluster_id[:8]}")
    delay: Final = SettingsStorage.get(ESettingKey.REGISTRY_REQ_DELAY)

    if not is_allowed_start_cache(state):
        logger.warning("Check action already running. Exiting.")
        return result

    try:
        logger.info("Starting swarm cluster check")
        cache.set({"status": EActionStatus.PREPARING})

        raw_services = await client.service.list()
        raw_by_name: dict[str, dict] = {}
        for svc in raw_services:
            name = svc.get("Spec", {}).get("Name", "")
            if name:
                raw_by_name[name] = svc

        async with async_session_maker() as session:
            stmt = select(SwarmServicesModel).where(
                SwarmServicesModel.swarm_cluster_id == cluster_id,
            )
            if not manual:
                stmt = stmt.where(SwarmServicesModel.check_enabled.is_(True))
            db_rows = (await session.execute(stmt)).scalars().all()

        cache.update({"status": EActionStatus.CHECKING})

        for db_row in db_rows:
            svc_result = SwarmServiceActionResult(
                service_name=db_row.name,
                service_id=db_row.name,
            )

            raw = raw_by_name.get(db_row.name)
            if not raw:
                logger.warning(f"Service {db_row.name} not found in live list, skipping")
                result.items.append(svc_result)
                continue

            svc_result.service_id = raw.get("ID", db_row.name)

            try:
                image_raw = (
                    raw.get("Spec", {})
                    .get("TaskTemplate", {})
                    .get("ContainerSpec", {})
                    .get("Image", "")
                )
                if not image_raw:
                    logger.warning(f"No image for service {db_row.name}, skipping")
                    result.items.append(svc_result)
                    continue

                base_spec, local_digest = _split_image_spec(image_raw)
                svc_result.image_spec = base_spec
                svc_result.local_digest = local_digest

                if not local_digest:
                    logger.warning(
                        f"No digest in image spec for {db_row.name}, skipping registry check"
                    )
                    result.items.append(svc_result)
                    continue

                logger.info(f"Checking {db_row.name}: spec={base_spec}")

                remote_digest: str | None = None
                try:
                    remote_digest = await get_image_remote_digest(base_spec, local_digest)
                except Exception:
                    logger.exception(f"Failed to get remote digest for {db_row.name}")
                finally:
                    await asyncio.sleep(jitter(delay))

                svc_result.remote_digest = remote_digest
                logger.info(f"Remote digest for {db_row.name}: {remote_digest}")

                result_lit: SwarmServiceCheckResultType = "not_available"
                if remote_digest and remote_digest != local_digest:
                    if db_row.remote_digests and remote_digest in db_row.remote_digests:
                        result_lit = "available(notified)"
                    else:
                        result_lit = "available"
                svc_result.result = result_lit
                logger.info(f"Check result for {db_row.name}: {result_lit}")

                async with async_session_maker() as session:
                    db_item = await get_or_create_service_db(session, cluster_id, db_row.name)
                    db_item.update_available = result_lit != "not_available"
                    db_item.checked_at = now()
                    db_item.image_id = base_spec
                    db_item.local_digests = [local_digest] if local_digest else []
                    db_item.remote_digests = [remote_digest] if remote_digest else []
                    await session.commit()

            except Exception:
                logger.exception(f"Failed to check service {db_row.name}")

            result.items.append(svc_result)

        cache.update({"status": EActionStatus.DONE, "result": result})
        return result

    except Exception:
        logger.exception(f"Failed to check swarm cluster {cluster_id}")
        cache.update({"status": EActionStatus.ERROR})
        return result


async def check_swarm_service(
    cluster_id: str,
    service_name: str,
    client: SwarmAgentClient,
) -> None:
    """Check a single swarm service for image updates (always treated as manual)."""
    logger = logging.getLogger(f"check_swarm_service.{cluster_id[:8]}.{service_name}")
    delay: Final = SettingsStorage.get(ESettingKey.REGISTRY_REQ_DELAY)
    cache_key: Final = get_swarm_service_cache_key(cluster_id, service_name)
    cache: Final = ProgressCache[SwarmClusterActionProgress](cache_key)

    if not is_allowed_start_cache(cache.get()):
        logger.warning(f"Check for {service_name} already running. Exiting.")
        return

    cache.set({"status": EActionStatus.PREPARING})

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

        image_raw: str = (
            raw.get("Spec", {})
            .get("TaskTemplate", {})
            .get("ContainerSpec", {})
            .get("Image", "")
        )
        if not image_raw:
            logger.warning(f"No image for service {service_name}")
            return

        base_spec, local_digest = _split_image_spec(image_raw)
        if not local_digest:
            logger.warning(f"No digest in image spec for {service_name}")
            return

        logger.info(f"Checking {service_name}: spec={base_spec}")

        cache.update({"status": EActionStatus.CHECKING})

        remote_digest: str | None = None
        try:
            remote_digest = await get_image_remote_digest(base_spec, local_digest)
        except Exception:
            logger.exception(f"Failed to get remote digest for {service_name}")
        finally:
            await asyncio.sleep(jitter(delay))

        update_available = bool(remote_digest and remote_digest != local_digest)

        async with async_session_maker() as session:
            db_item = await get_or_create_service_db(session, cluster_id, service_name)
            db_item.update_available = update_available
            db_item.checked_at = now()
            db_item.image_id = base_spec
            db_item.local_digests = [local_digest] if local_digest else []
            db_item.remote_digests = [remote_digest] if remote_digest else []
            await session.commit()

        logger.info(f"Check result for {service_name}: update_available={update_available}")
        cache.update({"status": EActionStatus.DONE})

    except Exception:
        logger.exception(f"Failed to check service {service_name}")
        cache.update({"status": EActionStatus.ERROR})


async def check_all_swarm_clusters(manual: bool = False) -> list[SwarmClusterActionResult]:
    """
    Check all registered swarm clusters.
    Piggy-backed onto the container check schedule.
    """
    from backend.core.agent_client import AgentClientManager

    cache: Final = ProgressCache[AllSwarmActionProgress](ALL_SWARM_CLUSTERS_STATUS_KEY)
    state: Final = cache.get()
    logger: Final = logging.getLogger("check_all_swarm_clusters")

    if not is_allowed_start_cache(state):
        logger.warning("Swarm check already running. Exiting.")
        return []

    try:
        cache.set({"status": EActionStatus.PREPARING})
        logger.info("Starting swarm cluster checks")

        async with async_session_maker() as session:
            stmt = select(HostsModel).where(
                HostsModel.enabled.is_(True),
                HostsModel.swarm_cluster_id.isnot(None),
            )
            hosts = (await session.execute(stmt)).scalars().all()

        # Deduplicate — one check per cluster_id (use first reachable host)
        seen_clusters: set[str] = set()
        cluster_host_map: dict[str, HostsModel] = {}
        for h in hosts:
            cid = h.swarm_cluster_id
            if cid and cid not in seen_clusters:
                seen_clusters.add(cid)
                cluster_host_map[cid] = h

        cache.update({"status": EActionStatus.CHECKING})
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
                res = await check_swarm_cluster(cluster_id, cluster_name, client, manual)
                results.append(res)
            except Exception:
                logger.exception(f"Failed to check swarm cluster {cluster_id}")

        cache.update(
            {
                "status": EActionStatus.DONE,
                "result": {r.cluster_id: r for r in results},
            }
        )
        return results

    except Exception:
        cache.update({"status": EActionStatus.ERROR})
        logger.exception("Error during swarm cluster checks")
        return []
