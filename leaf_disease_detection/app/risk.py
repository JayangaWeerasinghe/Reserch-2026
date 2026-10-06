from typing import Dict, Optional
import numpy as np

DISEASE_BASE_RISK = {
    "Healthy": 0.0,
    "Bacterial_Blight": 8.0,
    "Brown_Spot": 6.0,
    "Leaf_Blast": 10.0,
}
GROWTH_STAGE_FACTOR = {
    "Seedling": 0.75,
    "Tillering": 1.00,
    "Panicle Initiation": 1.15,
    "Booting": 1.20,
    "Flowering": 1.30,
    "Grain Filling": 1.15,
    "Maturity": 0.70,
    "Unknown": 1.00,
}

def severity_label(value: float) -> str:
    if value <= 5: return "Negligible"
    if value <= 15: return "Mild"
    if value <= 30: return "Moderate"
    if value <= 50: return "Severe"
    return "Critical"

def calculate_risk(
    disease: str,
    severity_percentage: float,
    affected_field_percentage: float,
    growth_stage: str,
    weather: Dict,
    area_acres: float,
    expected_yield_kg_per_acre: Optional[float],
    treatment_applied: bool,
) -> Dict:
    humidity = weather.get("history_mean_humidity_pct", 75)
    rainfall = weather.get("history_total_rainfall_mm", 0)
    temperature = weather.get("history_mean_temperature_c", 28)
    forecast_rainfall = weather.get("forecast_total_rainfall_mm", 0)

    humidity_risk = np.clip((humidity - 65) / 30, 0, 1)
    rainfall_risk = np.clip(rainfall / 100, 0, 1)
    temperature_risk = max(0.0, 1.0 - abs(temperature - 27.0) / 10.0)
    forecast_risk = np.clip(forecast_rainfall / 60, 0, 1)

    climate_score = 100 * (
        0.35 * humidity_risk +
        0.25 * rainfall_risk +
        0.25 * temperature_risk +
        0.15 * forecast_risk
    )

    if disease == "Healthy":
        loss = 0.0
    else:
        loss = (
            DISEASE_BASE_RISK.get(disease, 7.0)
            + 0.32 * severity_percentage
            + 0.18 * affected_field_percentage
            + 0.12 * climate_score
        ) * GROWTH_STAGE_FACTOR.get(growth_stage, 1.0)

        if treatment_applied:
            loss *= 0.82
        loss = float(np.clip(loss, 0, 80))

    margin = max(4.0, loss * 0.25)
    lower = float(np.clip(loss - margin, 0, 100))
    upper = float(np.clip(loss + margin, 0, 100))

    result = {
        "predicted_loss_percentage": round(loss, 2),
        "loss_range_percentage": [round(lower, 2), round(upper, 2)],
        "climate_risk_score": round(float(climate_score), 2),
        "risk_level": "Low" if loss < 5 else "Moderate" if loss < 15 else "High" if loss < 30 else "Critical",
        "warning": "Research estimate only. Calibrate using verified field harvest outcomes.",
        "calculation_breakdown": {
            "climate": {
                "history_mean_temperature_c": round(temperature, 2),
                "history_mean_humidity_pct": round(humidity, 2),
                "history_total_rainfall_mm": round(rainfall, 2),
                "forecast_total_rainfall_mm": round(forecast_rainfall, 2),
                "normalized_components": {
                    "humidity_risk": round(float(humidity_risk), 4),
                    "rainfall_risk": round(float(rainfall_risk), 4),
                    "temperature_risk": round(float(temperature_risk), 4),
                    "forecast_rain_risk": round(float(forecast_risk), 4),
                },
                "weights": {
                    "humidity": 0.35,
                    "rainfall": 0.25,
                    "temperature": 0.25,
                    "forecast_rain": 0.15
                },
                "weighted_contributions": {
                    "humidity": round(float(0.35 * humidity_risk * 100), 4),
                    "rainfall": round(float(0.25 * rainfall_risk * 100), 4),
                    "temperature": round(float(0.25 * temperature_risk * 100), 4),
                    "forecast_rain": round(float(0.15 * forecast_risk * 100), 4)
                },
                "climate_risk_score": round(float(climate_score), 2)
            },
            "loss": {
                "disease_base_risk": DISEASE_BASE_RISK.get(disease, 0.0),
                "severity_contribution": round(0.32 * severity_percentage, 4) if disease != "Healthy" else 0.0,
                "affected_field_contribution": round(0.18 * affected_field_percentage, 4) if disease != "Healthy" else 0.0,
                "climate_contribution": round(0.12 * float(climate_score), 4) if disease != "Healthy" else 0.0,
                "raw_loss_before_growth_stage": round((
                    DISEASE_BASE_RISK.get(disease, 7.0)
                    + 0.32 * severity_percentage
                    + 0.18 * affected_field_percentage
                    + 0.12 * climate_score
                ) if disease != "Healthy" else 0.0, 4),
                "growth_stage": growth_stage,
                "growth_stage_factor": GROWTH_STAGE_FACTOR.get(growth_stage, 1.0),
                "treatment_applied": treatment_applied,
                "treatment_factor": 0.82 if treatment_applied else 1.0,
                "predicted_loss_percentage": round(loss, 2)
            }
        }
    }

    if expected_yield_kg_per_acre:
        healthy = area_acres * expected_yield_kg_per_acre
        estimated_loss_kg = healthy * loss / 100
        result["expected_healthy_yield_kg"] = round(healthy, 2)
        result["estimated_loss_kg"] = round(estimated_loss_kg, 2)
        result["estimated_loss_range_kg"] = [
            round(healthy * lower / 100, 2),
            round(healthy * upper / 100, 2),
        ]
        result["calculation_breakdown"]["estimated_loss"] = {
            "field_area_acres": area_acres,
            "expected_yield_kg_per_acre": expected_yield_kg_per_acre,
            "expected_healthy_yield_kg": round(healthy, 2),
            "predicted_loss_percentage": round(loss, 2),
            "estimated_loss_kg": round(estimated_loss_kg, 2)
        }

    return result
