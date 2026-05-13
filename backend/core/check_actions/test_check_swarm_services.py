
from backend.core.check_actions.check_swarm_services import _split_image_spec


class TestSplitImageSpec:
    def test_splits_digest(self):
        base, digest = _split_image_spec("nginx:latest@sha256:abc123")
        assert base == "nginx:latest"
        assert digest == "sha256:abc123"

    def test_no_digest(self):
        base, digest = _split_image_spec("nginx:latest")
        assert base == "nginx:latest"
        assert digest is None

    def test_multiple_at_signs_splits_on_last(self):
        # edge case: image name theoretically can't have @, but digest can have sub-parts
        base, digest = _split_image_spec("reg.io/repo/img:tag@sha256:deadbeef")
        assert base == "reg.io/repo/img:tag"
        assert digest == "sha256:deadbeef"

    def test_digest_only(self):
        base, digest = _split_image_spec("nginx@sha256:abc")
        assert base == "nginx"
        assert digest == "sha256:abc"
