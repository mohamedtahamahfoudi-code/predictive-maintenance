from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_predict_returns_valid_probability():
    payload = {
        "air_temperature_k": 298.9,
        "process_temperature_k": 309.3,
        "rotational_speed_rpm": 1500,
        "torque_nm": 40.0,
        "tool_wear_min": 100,
        "type_L": 0,
        "type_M": 1,
        "type_H": 0
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert 0 <= data["failure_probability"] <= 1
    assert data["risk_band"] in ["low", "high"]