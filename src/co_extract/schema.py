"""Schemas: what the extractor returns (Extraction) and what the pipeline outputs (Result)."""

from datetime import date
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, Field


class ReasonCategory(str, Enum):
    owner_request = "owner_request"
    design_change = "design_change"
    unforeseen_condition = "unforeseen_condition"
    material_substitution = "material_substitution"
    code_compliance = "code_compliance"
    other = "other"


class ApprovalStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class LineItem(BaseModel):
    item: str | None = None
    qty: float | None = None
    unit: str | None = None
    unit_cost: float | None = None
    total: float | None = None


class Extraction(BaseModel):
    """Raw extraction. Every field is optional: missing means null, never invented."""

    change_order_number: str | None = None
    project_name: str | None = None
    contractor: str | None = None
    owner: str | None = None
    date_issued: date | None = None
    description: str | None = None
    reason: str | None = None
    reason_category: ReasonCategory | None = None
    cost_change: float | None = None
    currency: str | None = None
    original_contract_sum: float | None = None
    contract_sum_before: float | None = None
    revised_contract_sum: float | None = None
    schedule_impact_days: int | None = None
    approval_status: ApprovalStatus | None = None
    approved_by: str | None = None
    date_approved: date | None = None
    line_items: list[LineItem] = Field(default_factory=list)


SCALAR_FIELDS = [f for f in Extraction.model_fields if f != "line_items"]

# Field descriptions, shown to the LLM.
FIELD_GUIDE = {
    "change_order_number": "Identifier of THIS change order, as printed (e.g. 'CO-014', '4').",
    "project_name": "Project name.",
    "contractor": "Contractor company name.",
    "owner": "Owner / client organisation paying for the work (e.g. 'City of X'), not a council, board or department.",
    "date_issued": "Date this change order was issued/dated, YYYY-MM-DD. Not the contract date or a meeting date.",
    "description": "Short summary of what is changing, using the document's words. Ignore blank-form instructions such as 'Insert a detailed description...'.",
    "reason": "Why the change is needed, as stated in the document.",
    "reason_category": "One of: owner_request, design_change, unforeseen_condition, material_substitution, code_compliance, other.",
    "cost_change": "Net change in contract price from THIS change order. Negative for decreases/credits/deducts. 0 if explicitly no cost change.",
    "currency": "ISO currency code, e.g. USD, only if a currency symbol or code appears.",
    "original_contract_sum": "Original contract sum/price before any change orders.",
    "contract_sum_before": "Contract sum immediately before THIS change order (after previous change orders).",
    "revised_contract_sum": "New contract sum including THIS change order.",
    "schedule_impact_days": "Days added to the contract time by THIS change order (negative if reduced, 0 if explicitly unchanged). If several milestones, use substantial completion.",
    "approval_status": "approved only if the OWNER's signature/approval is actually filled in; pending if owner signature lines are blank or approval is requested/recommended; rejected; null if not determinable. Printed labels like 'Approved by' are not approval.",
    "approved_by": "Name only (no title) of the person who approved for the owner, only if approved.",
    "date_approved": "Date of owner approval, YYYY-MM-DD.",
    "line_items": "List of priced items in THIS change order: {item, qty, unit, unit_cost, total}. qty is the quantity added/deducted by this change order (not the original contract quantity). Copy numbers as printed.",
}


# ---------------------------------------------------------------- output schema

T = TypeVar("T")


class Scored(BaseModel, Generic[T]):
    value: T | None = None
    confidence: float = Field(ge=0, le=1)
    signals: dict[str, float] = Field(default_factory=dict)


class ScoredLineItem(LineItem):
    confidence: float = Field(ge=0, le=1)
    signals: dict[str, float] = Field(default_factory=dict)


class Check(BaseModel):
    check: str
    fields: list[str]
    passed: bool
    message: str


class Result(BaseModel):
    change_order_number: Scored[str]
    project_name: Scored[str]
    contractor: Scored[str]
    owner: Scored[str]
    date_issued: Scored[date]
    description: Scored[str]
    reason: Scored[str]
    reason_category: Scored[ReasonCategory]
    cost_change: Scored[float]
    currency: Scored[str]
    original_contract_sum: Scored[float]
    contract_sum_before: Scored[float]
    revised_contract_sum: Scored[float]
    schedule_impact_days: Scored[int]
    approval_status: Scored[ApprovalStatus]
    approved_by: Scored[str]
    date_approved: Scored[date]
    line_items: list[ScoredLineItem]
    validation: list[Check]
    meta: dict
