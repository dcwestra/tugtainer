from unittest.mock import MagicMock

from backend.modules.swarm.swarm_util import (
    _extract_service_image,
    _extract_service_mode,
    _extract_update_status,
    display_cluster_name,
    map_service_schema,
)


def _make_host(cluster_id=None, cluster_name=None, name="host-1"):
    h = MagicMock()
    h.swarm_cluster_id = cluster_id
    h.swarm_cluster_name = cluster_name
    h.name = name
    return h


def _make_db(
    id=1,
    check_enabled=False,
    update_enabled=False,
    update_available=False,
    checked_at=None,
    updated_at=None,
):
    db = MagicMock()
    db.id = id
    db.check_enabled = check_enabled
    db.update_enabled = update_enabled
    db.update_available = update_available
    db.checked_at = checked_at
    db.updated_at = updated_at
    return db


class TestDisplayClusterName:
    def test_uses_cluster_name_when_set(self):
        h = _make_host(cluster_id="abc123", cluster_name="prod")
        assert display_cluster_name(h) == "prod"

    def test_falls_back_to_cluster_id_prefix(self):
        h = _make_host(cluster_id="abc12345def", cluster_name=None)
        assert display_cluster_name(h) == "swarm-abc12345"

    def test_falls_back_to_host_name_when_no_cluster_id(self):
        h = _make_host(cluster_id=None, cluster_name=None, name="my-host")
        assert display_cluster_name(h) == "my-host"


class TestExtractServiceImage:
    def test_extracts_image(self):
        svc = {"Spec": {"TaskTemplate": {"ContainerSpec": {"Image": "nginx:latest@sha256:abc"}}}}
        assert _extract_service_image(svc) == "nginx:latest@sha256:abc"

    def test_missing_key_returns_none(self):
        assert _extract_service_image({}) is None
        assert _extract_service_image({"Spec": {}}) is None


class TestExtractServiceMode:
    def test_replicated_with_replicas(self):
        svc = {"Spec": {"Mode": {"Replicated": {"Replicas": 3}}}}
        mode, replicas = _extract_service_mode(svc)
        assert mode == "replicated"
        assert replicas == 3

    def test_global_mode(self):
        svc = {"Spec": {"Mode": {"Global": {}}}}
        mode, replicas = _extract_service_mode(svc)
        assert mode == "global"
        assert replicas is None

    def test_unknown_mode_defaults(self):
        mode, replicas = _extract_service_mode({})
        assert mode == "replicated"
        assert replicas is None


class TestExtractUpdateStatus:
    def test_extracts_state(self):
        svc = {"UpdateStatus": {"State": "updating"}}
        assert _extract_update_status(svc) == "updating"

    def test_missing_returns_none(self):
        assert _extract_update_status({}) is None


class TestMapServiceSchema:
    def test_maps_with_db(self):
        svc = {
            "ID": "svcid123",
            "Spec": {
                "Name": "web",
                "Mode": {"Replicated": {"Replicas": 2}},
                "TaskTemplate": {"ContainerSpec": {"Image": "nginx:latest"}},
            },
        }
        db = _make_db(id=5, check_enabled=True, update_available=True)
        result = map_service_schema(svc, db)
        assert result.name == "web"
        assert result.service_id == "svcid123"
        assert result.image == "nginx:latest"
        assert result.replicas == 2
        assert result.mode == "replicated"
        assert result.id == 5
        assert result.check_enabled is True
        assert result.update_available is True

    def test_maps_without_db(self):
        svc = {"ID": "svcid", "Spec": {"Name": "worker"}}
        result = map_service_schema(svc, None)
        assert result.name == "worker"
        assert result.id is None
        assert result.check_enabled is None
