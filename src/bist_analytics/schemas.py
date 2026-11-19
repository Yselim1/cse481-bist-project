"""Financial observations retain period, currency, publication and source vintage.

Also defines the 8-label educational action space, the 5-state data-quality gate,
and the evidence-bundle schema that the fine-tuned LLM must commit to.
"""

from datetime import date
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

# --- 8-label educational action space ---------------------------------------------------
EDUCATIONAL_LABELS = (
    "HOLD",
    "WATCH",
    "INVESTIGATE",
    "POTENTIAL_CATCH_UP_CANDIDATE",
    "TECHNICAL_REVERSAL_CANDIDATE",
    "FUNDAMENTAL_IMPROVEMENT_CANDIDATE",
    "REJECT_SIGNAL",
    "ANALYSIS_UNSAFE",
)
EducationalLabel = Literal[
    "HOLD",
    "WATCH",
    "INVESTIGATE",
    "POTENTIAL_CATCH_UP_CANDIDATE",
    "TECHNICAL_REVERSAL_CANDIDATE",
    "FUNDAMENTAL_IMPROVEMENT_CANDIDATE",
    "REJECT_SIGNAL",
    "ANALYSIS_UNSAFE",
]

# Internal BUY/SELL/HOLD actions map to educational labels for reporting/agent output.
INTERNAL_TO_EDUCATIONAL = {
    "BUY": "TECHNICAL_REVERSAL_CANDIDATE",
    "SELL": "REJECT_SIGNAL",
    "HOLD": "HOLD",
}


# --- 5-state data-quality gate ----------------------------------------------------------
GATE_STATES = ("PASS", "PASS_WITH_WARNINGS", "INVESTIGATE", "ANALYSIS_UNSAFE", "HARD_BLOCK")
GateStatus = Literal["PASS", "PASS_WITH_WARNINGS", "INVESTIGATE", "ANALYSIS_UNSAFE", "HARD_BLOCK"]


class EvidenceItem(BaseModel):
    """A single piece of evidence captured for an answer.

    `observed`: available to the agent for context.
    `committed`: cited in the final answer; audited by the evidence completeness metric.
    """
    model_config = ConfigDict(extra="forbid")
    evidence_id: str
    source_tool: str
    source_document: str | None = None
    value: Any | None = None
    unit: str | None = None
    as_of: str | None = None
    note: str | None = None


class EvidenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str
    as_of: str
    observed: list[EvidenceItem] = Field(default_factory=list)
    committed: list[EvidenceItem] = Field(default_factory=list)
    gate_status: GateStatus
    educational_label: EducationalLabel
    reason: str
    warnings: list[str] = Field(default_factory=list)


class AgentAnswer(BaseModel):
    """Structured answer envelope the fine-tuned agent must emit."""
    model_config = ConfigDict(extra="forbid")
    question: str
    ticker: str
    as_of: str
    educational_label: EducationalLabel
    gate_status: GateStatus
    committed_evidence_ids: list[str]
    explanation: str
    warnings: list[str] = Field(default_factory=list)
    tool_calls: list[dict] = Field(default_factory=list)

METRICS = {
    "revenue", "gross_profit", "ebitda", "operating_profit", "net_profit", "cash",
    "financial_debt", "net_debt", "total_assets", "equity", "operating_cash_flow",
    "investing_cash_flow", "financing_cash_flow", "current_assets", "inventories",
    "current_liabilities", "shares_outstanding", "pe", "pb", "ev_ebitda", "roe", "roa",
    "ebitda_margin", "net_margin", "net_debt_ebitda", "debt_equity", "current_ratio", "quick_ratio",
}
FLOW_METRICS = {
    "revenue", "gross_profit", "ebitda", "operating_profit", "net_profit",
    "operating_cash_flow", "investing_cash_flow", "financing_cash_flow",
}


class FinancialObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: Literal["THYAO.IS"] = "THYAO.IS"
    metric: str
    period_end: date
    period_type: Literal["annual", "ytd", "quarter", "ttm", "instant", "ratio"]
    value: float | None = Field(default=None, allow_inf_nan=False)
    currency: Literal["USD", "TRY"]
    scale: float = Field(1, gt=0)
    unit: Literal["money", "shares", "ratio", "fraction"] = "money"
    published_at: date | None = None
    assumed_published_at: date | None = None
    source_url: str
    source_reference: str
    retrieved_at: date
    vintage_verified: bool = False
    accounting_basis: str = "IFRS-consolidated"
    notes: str = ""

    @model_validator(mode="after")
    def validate_observation(self):
        if self.metric not in METRICS:
            raise ValueError(f"Unknown metric: {self.metric}")
        release = self.published_at or self.assumed_published_at
        if release is None:
            raise ValueError("A verified or explicitly assumed release date is required")
        if release < self.period_end:
            raise ValueError("Publication precedes financial period end")
        if self.retrieved_at < release:
            raise ValueError("Retrieval precedes publication")
        host = urlparse(self.source_url).hostname or ""
        if host != "fintables.com" and not host.endswith(".fintables.com"):
            raise ValueError("Historical fundamental source must be Fintables")
        if not self.source_reference.strip():
            raise ValueError("A source/export and release/vintage evidence reference is required")
        if self.vintage_verified and self.published_at is None:
            raise ValueError("Verified vintages require verified publication dates")
        return self
