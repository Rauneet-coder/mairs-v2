from __future__ import annotations
from enum import Enum
from datetime import datetime, timezone
from uuid import uuid4
from typing import Literal, TypedDict, Optional
from pydantic import BaseModel, Field

class Severity(str, Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

class AlertEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    severity: Severity
    service: str
    component: str
    anomaly: str
    business_impact: Literal["low", "medium", "high"]
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_metrics: dict

class HistoricalMatch(BaseModel):
    incident_id: str
    title: str
    description: str
    root_cause: str
    resolution_steps: list[str]
    severity: str
    time_to_resolve_minutes: int
    similarity_score: float

class RunbookStep(BaseModel):
    step: int
    action: str
    command: str | None = None
    duration_minutes: int
    historical_ref: str | None = None
    auto_executable: bool = False

class Runbook(BaseModel):
    steps: list[RunbookStep]
    estimated_resolution_minutes: int
    confidence: float
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CausalStep(BaseModel):
    step: int
    event: str
    service: str
    lag_seconds: int

class ImpactScope(BaseModel):
    affected_services: list[str]
    estimated_users_affected: int
    blast_radius: Literal["low", "moderate", "high", "critical"]

class RCAResult(BaseModel):
    trigger: dict
    propagation: list[CausalStep]
    impact: ImpactScope
    root_cause_category: str
    confidence: float
    similar_incident_ref: str | None = None
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class HealingAction(BaseModel):
    action: str
    target: str
    status: Literal["success", "failed", "skipped"]
    output: str
    duration_ms: int

class HealingResult(BaseModel):
    actions_attempted: int
    actions_succeeded: int
    actions_failed: int
    actions_log: list[HealingAction]
    metrics_before: dict
    metrics_after: dict
    improvement_percent: float | None = None
    dry_run: bool = True

class CapacityForecast(BaseModel):
    service: str
    metric: str
    current_value: float
    threshold: float
    predicted_breach_hours: float
    trend: Literal["increasing", "decreasing", "volatile", "stable"]
    confidence: float
    recommendation: str

class CapacityReport(BaseModel):
    forecasts: list[CapacityForecast]
    analysis_window_hours: int = 168
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AgentEvent(BaseModel):
    agent: str
    status: Literal["running", "done", "error"]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict | None = None

class PipelineState(TypedDict):
    raw_metrics: dict
    alert_event: AlertEvent | None
    historical_matches: list[HistoricalMatch]
    rca_result: RCAResult | None
    runbook: Runbook | None
    healing_result: HealingResult | None
    notification_sent: bool
    pipeline_id: str
    pipeline_start_time: float
    error: str | None
