import joblib
import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel, Field

# Load the trained model once, when the API starts
model = joblib.load("models/xgb_model.pkl")

app = FastAPI(title="Predictive Maintenance API")


# ---- Define what a valid request looks like ----
class MachineReading(BaseModel):
    air_temperature_k: float = Field(..., example=298.9)
    process_temperature_k: float = Field(..., example=309.3)
    rotational_speed_rpm: int = Field(..., example=1500)
    torque_nm: float = Field(..., example=40.0)
    tool_wear_min: int = Field(..., example=100)
    type_L: int = Field(..., example=0)
    type_M: int = Field(..., example=1)
    type_H: int = Field(..., example=0)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict")
def predict(reading: MachineReading):
    # Recreate the engineered features, same as in the notebook
    temp_gap = reading.process_temperature_k - reading.air_temperature_k
    high_wear = 1 if reading.tool_wear_min > 200 else 0
    low_temp_gap = 1 if temp_gap < 8.7 else 0

    # Build a single-row DataFrame matching the model's expected columns
    input_df = pd.DataFrame([{
        "air_temperature_k": reading.air_temperature_k,
        "process_temperature_k": reading.process_temperature_k,
        "rotational_speed_rpm": reading.rotational_speed_rpm,
        "torque_nm": reading.torque_nm,
        "tool_wear_min": reading.tool_wear_min,
        "temp_gap": temp_gap,
        "high_wear": high_wear,
        "low_temp_gap": low_temp_gap,
        "type_H": reading.type_H,
        "type_L": reading.type_L,
        "type_M": reading.type_M,
    }])

    probability = model.predict_proba(input_df)[0][1]
    risk_band = "high" if probability > 0.5 else "low"

    return {
        "failure_probability": round(float(probability), 4),
        "risk_band": risk_band
    }