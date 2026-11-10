"""The shape of every request the service accepts and every reply it returns."""

from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

from config import config

TechnologyFilter = Literal[tuple(config.QUEUE_TECHNOLOGY_OPTIONS)]
ReviewStatusValue = Literal[tuple(config.REVIEW_STATUS_OPTIONS)]
DecisionValue = Literal[tuple(config.DECISIONS)]

CoordinatorRequestText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=config.COORDINATOR_REQUEST_MINIMUM_CHARACTERS,
        max_length=config.COORDINATOR_REQUEST_MAXIMUM_CHARACTERS,
    ),
]
DecisionReasonText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=config.DECISION_REASON_MINIMUM_CHARACTERS,
        max_length=config.DECISION_REASON_MAXIMUM_CHARACTERS,
    ),
]
QuestionText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=config.CHAT_QUESTION_MINIMUM_CHARACTERS,
        max_length=config.CHAT_QUESTION_MAXIMUM_CHARACTERS,
    ),
]


class SignInRequest(BaseModel):
    username: str
    password: str


class SignedInUserResponse(BaseModel):
    username: str
    display_name: str
    role: str
    session_token: str
    pages: list[str]
    areas: list[str]


class SignedOutResponse(BaseModel):
    username: str
    signed_out: bool


class QueueRow(BaseModel):
    queue_position: int
    application_reference: str
    technology: str
    technology_label: str
    source_portal: str | None
    premises_type: str | None
    urgency: str | None
    document_count: int
    requirements_met_count: int
    requirements_not_met_count: int
    requirements_not_documented_count: int
    network_trigger_count: int
    rating_stated: bool
    assessment: str
    decisions_open: list[str]
    network_work_likelihood: float
    likelihood_band: str
    expected_working_days: int
    delay_expected: bool | None
    disagreement_count: int


class ApplicationDetailResponse(BaseModel):
    queue_position: int
    application: dict
    application_documents: list[dict]
    screening: dict
    evidence_findings: list[dict]
    disagreements: list[dict]
    likelihood: dict
    duration: dict
    duration_text: str


class ReviewRequest(BaseModel):
    application_reference: str
    coordinator_request: CoordinatorRequestText


class DecisionRequest(BaseModel):
    decision: DecisionValue
    decision_reason: DecisionReasonText


class ReviewRecordResponse(BaseModel):
    review_id: str
    run_id: str
    thread_id: str | None
    application_reference: str
    technology: str
    urgency: str | None
    standard_document: str
    coordinator_id: str | None
    coordinator_request: str
    status: str
    llm_call_count: int | None
    requirements: list[dict]
    requirements_met_count: int
    requirements_not_met_count: int
    requirements_not_documented_count: int
    network_triggers: list[str]
    rating_stated: bool
    assessment: str
    decisions_open: list[str]
    evidence: list[dict]
    disagreements: list[dict]
    network_work_likelihood: float
    likelihood_band: str
    expected_working_days: int
    planned_working_days: int | None
    delay_expected: bool | None
    duration_text: str
    review_plan_text: str
    requirements_analysis_text: str
    evidence_review_text: str
    prediction_analysis_text: str
    recommendation_text: str
    recommended_decision: str
    decision: str | None
    decided_by: str | None
    decided_by_role: str | None
    decision_reason: str | None
    installer_notice_text: str | None
    notice_details: dict | None
    household_notice_text: str | None
    assessment_brief: dict | None


class LlmCallRecord(BaseModel):
    agent_name: str
    model_name: str
    prompt_tokens: int
    response_tokens: int
    total_tokens: int
    latency_milliseconds: int


class CallBudgetResponse(BaseModel):
    review_id: str
    run_id: str
    calls: list[LlmCallRecord]
    call_count: int
    expected_call_count: int
    total_tokens: int
    total_latency_milliseconds: int


class ChatRequest(BaseModel):
    question: QuestionText


class ChatResponse(BaseModel):
    question_type: str
    application_reference: str | None
    substation_reference: str | None
    technology: str | None
    answer: str
    source_documents: list[str]
    closest_distance: float | None
    was_refused: bool


class ChatTurnResponse(BaseModel):
    turn_id: int
    username: str
    user_role: str
    question_text: str
    question_type: str
    application_reference: str | None
    substation_reference: str | None
    technology: str | None
    answer_text: str
    source_documents: list[str]
    closest_distance: float | None
    was_refused: bool
