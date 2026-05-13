"""Tests for the swarm cluster guard logic in hosts_router._populate_swarm_cluster_id."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.modules.hosts.hosts_router import _populate_swarm_cluster_id


def _make_host(id=1, name="swarm-host", cluster_name=None, cluster_id=None):
    h = MagicMock()
    h.id = id
    h.name = name
    h.swarm_cluster_id = cluster_id
    h.swarm_cluster_name = cluster_name
    return h


@pytest.mark.asyncio
async def test_populate_sets_cluster_id():
    host = _make_host()
    session = AsyncMock()

    info = MagicMock()
    info.cluster_id = "cluster-abc"
    info.cluster_label = None

    swarm_client = AsyncMock()
    swarm_client.swarm_info.info = AsyncMock(return_value=info)

    # No duplicate
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    with patch(
        "backend.modules.hosts.hosts_router.AgentClientManager.get_swarm_client",
        return_value=swarm_client,
    ):
        await _populate_swarm_cluster_id(host, session)

    assert host.swarm_cluster_id == "cluster-abc"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_populate_raises_on_duplicate():
    host = _make_host(id=2)
    session = AsyncMock()

    info = MagicMock()
    info.cluster_id = "cluster-abc"
    info.cluster_label = None

    swarm_client = AsyncMock()
    swarm_client.swarm_info.info = AsyncMock(return_value=info)

    existing = _make_host(id=1, name="other-host")
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing))
    )

    with patch(
        "backend.modules.hosts.hosts_router.AgentClientManager.get_swarm_client",
        return_value=swarm_client,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await _populate_swarm_cluster_id(host, session)

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_populate_uses_cluster_label_when_no_name():
    host = _make_host(cluster_name=None)
    session = AsyncMock()

    info = MagicMock()
    info.cluster_id = "cluster-abc"
    info.cluster_label = "production"

    swarm_client = AsyncMock()
    swarm_client.swarm_info.info = AsyncMock(return_value=info)

    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    with patch(
        "backend.modules.hosts.hosts_router.AgentClientManager.get_swarm_client",
        return_value=swarm_client,
    ):
        await _populate_swarm_cluster_id(host, session)

    assert host.swarm_cluster_name == "production"


@pytest.mark.asyncio
async def test_populate_skips_gracefully_on_agent_error():
    host = _make_host()
    session = AsyncMock()

    swarm_client = AsyncMock()
    swarm_client.swarm_info.info = AsyncMock(side_effect=Exception("connection refused"))

    with patch(
        "backend.modules.hosts.hosts_router.AgentClientManager.get_swarm_client",
        return_value=swarm_client,
    ):
        # Should not raise — logs the error and returns
        await _populate_swarm_cluster_id(host, session)

    session.commit.assert_not_awaited()
