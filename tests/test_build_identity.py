from fastapi.testclient import TestClient

from backend.app.factory import create_app


def test_build_identity_describes_runtime_and_real_features(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        response = client.get("/api/build-identity", headers={"host": "127.0.0.1:8740"})
        assert response.status_code == 200
        identity = response.json()
        assert "fractal-node-text" in identity["features"]
        assert "hermes-isolated-addition-oracle" in identity["features"]
        assert len(identity["sourceSha256"]) == 64
        assert identity["dataRoot"] == str(tmp_path.resolve())
