"""
streamlit_app.py

Dashboard frontend for the Predictive Maintenance API.
Sensor inputs live in the sidebar; the main panel shows a gauge-style
risk indicator, similar to a real industrial monitoring console.

Usage:
    streamlit run streamlit_app.py

Note: requires the FastAPI service to be running separately
(e.g. via `docker run -p 8000:8000 predictive-maintenance-api`
or `uvicorn api.main:app --reload`).
"""

import requests
import streamlit as st
import plotly.graph_objects as go

API_URL = "http://127.0.0.1:8000/predict"

st.set_page_config(
    page_title="Predictive Maintenance Dashboard",
    page_icon=":wrench:",
    layout="wide",
)

# ---- Minimal, safe styling (no full-page background override) ----
st.markdown(
    """
    <style>
        .block-container {
            padding-top: 4rem;
            max-width: 1100px;
        }
        [data-testid="stMetric"] {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 16px 20px;
        }
        .eyebrow {
            color: #64748b;
            font-size: 0.8rem;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            font-weight: 600;
            margin-bottom: 4px;
        }
        .stButton > button {
            background-color: #0f172a;
            color: white;
            font-weight: 600;
            border: none;
            border-radius: 6px;
            padding: 0.65rem 1.2rem;
            width: 100%;
        }
        .stButton > button:hover {
            background-color: #1e293b;
            color: white;
        }
        .verdict-card {
            border-radius: 10px;
            padding: 24px;
            text-align: center;
            font-weight: 700;
            font-size: 1.3rem;
        }
        .verdict-low {
            background-color: #f0fdf4;
            border: 1px solid #86efac;
            color: #166534;
        }
        .verdict-high {
            background-color: #fef2f2;
            border: 1px solid #fca5a5;
            color: #991b1b;
        }
        .verdict-card .detail {
            font-weight: 400;
            font-size: 0.85rem;
            display: block;
            margin-top: 6px;
            color: #475569;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---- Sidebar: sensor inputs ----
with st.sidebar:
    st.markdown('<p class="eyebrow">Machine Inputs</p>', unsafe_allow_html=True)
    st.header("Sensor Readings")

    machine_type = st.selectbox("Product Quality Tier", ["L", "M", "H"], index=0)
    air_temp = st.number_input("Air Temperature (K)", value=298.9, step=0.1)
    process_temp = st.number_input("Process Temperature (K)", value=309.3, step=0.1)
    rpm = st.number_input("Rotational Speed (rpm)", value=1500, step=10)
    torque = st.number_input("Torque (Nm)", value=40.0, step=0.5)
    tool_wear = st.number_input("Tool Wear (min)", value=100, step=5)

    st.write("")
    predict_clicked = st.button("Run Risk Assessment")

# ---- Main panel: header ----
st.markdown(
    '<p class="eyebrow">CNC Machining Unit - Condition Monitoring</p>',
    unsafe_allow_html=True,
)
st.title("Predictive Maintenance Dashboard")
st.caption(
    "Live equipment failure-risk estimation, powered by an XGBoost model "
    "trained on the AI4I 2020 industrial dataset."
)
st.divider()

if not predict_clicked:
    st.info(
        "Enter sensor readings in the sidebar and click "
        "**Run Risk Assessment** to see a live prediction."
    )

if predict_clicked:
    payload = {
        "air_temperature_k": air_temp,
        "process_temperature_k": process_temp,
        "rotational_speed_rpm": int(rpm),
        "torque_nm": torque,
        "tool_wear_min": int(tool_wear),
        "type_L": 1 if machine_type == "L" else 0,
        "type_M": 1 if machine_type == "M" else 0,
        "type_H": 1 if machine_type == "H" else 0,
    }

    try:
        response = requests.post(API_URL, json=payload, timeout=5)
        response.raise_for_status()
        result = response.json()

        probability = result["failure_probability"]
        risk_band = result["risk_band"]

        col_gauge, col_metrics = st.columns([1.1, 1])

        with col_gauge:
            fig = go.Figure(
                go.Indicator(
                    mode="gauge+number",
                    value=probability * 100,
                    number={"suffix": "%", "font": {"size": 44}},
                    domain={"x": [0, 1], "y": [0, 1]},
                    gauge={
                        "axis": {"range": [0, 100], "tickwidth": 1},
                        "bar": {"color": "#0f172a", "thickness": 0.25},
                        "steps": [
                            {"range": [0, 30], "color": "#dcfce7"},
                            {"range": [30, 60], "color": "#fef9c3"},
                            {"range": [60, 100], "color": "#fee2e2"},
                        ],
                        "threshold": {
                            "line": {"color": "#dc2626", "width": 3},
                            "thickness": 0.8,
                            "value": 50,
                        },
                    },
                )
            )
            fig.update_layout(
                height=280,
                margin=dict(l=20, r=20, t=30, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                font={"family": "Arial"},
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_metrics:
            st.write("")
            st.write("")
            if risk_band == "high":
                st.markdown(
                    '<div class="verdict-card verdict-high">HIGH RISK'
                    '<span class="detail">Recommend maintenance inspection</span>'
                    "</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="verdict-card verdict-low">LOW RISK'
                    '<span class="detail">Machine operating within normal range</span>'
                    "</div>",
                    unsafe_allow_html=True,
                )

            st.write("")
            m1, m2 = st.columns(2)
            m1.metric("Tool Wear", f"{tool_wear} min", delta="Threshold: 200 min", delta_color="off")
            m2.metric("Temp Gap", f"{process_temp - air_temp:.1f} K", delta="Threshold: 8.7 K", delta_color="off")

        st.divider()
        with st.expander("View raw sensor payload sent to API"):
            st.json(payload)

    except requests.exceptions.ConnectionError:
        st.error(
            "Could not reach the prediction API. Make sure it's running at "
            f"`{API_URL}` - e.g. via `docker run -p 8000:8000 "
            "predictive-maintenance-api`."
        )
    except Exception as e:
        st.error(f"Unexpected error: {e}")

st.divider()
st.caption(
    "Portfolio demo project - predictions are based on a model trained on "
    "synthetic industrial data (AI4I 2020) and are not intended for real "
    "operational decisions."
)