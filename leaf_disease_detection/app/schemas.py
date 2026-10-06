from typing import Optional
from dataclasses import dataclass

@dataclass
class ContextInput:
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    field_area_acres: float = 1.0
    affected_field_percentage: float = 0.0
    rice_variety: str = "Unknown"
    growth_stage: str = "Unknown"
    expected_yield_kg_per_acre: Optional[float] = None
    treatment_applied: bool = False

@dataclass
class FeedbackInput:
    farmer_confirmation: Optional[str] = None
    expert_validated_disease: Optional[str] = None
    actual_harvest_kg: Optional[float] = None
    expected_healthy_harvest_kg: Optional[float] = None
    approved_for_training: bool = False
