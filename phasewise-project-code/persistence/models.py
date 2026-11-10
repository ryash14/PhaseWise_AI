"""The six tables everything the system is asked to account for is kept in."""

from sqlalchemy import JSON, Boolean, Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base

from config import config

Base = declarative_base()


class UserAccount(Base):
    """One person who signs in, with the stored form of their password."""

    __tablename__ = config.USER_ACCOUNTS_TABLE

    username = Column(String, primary_key=True)
    display_name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    password_salt = Column(String, nullable=False)
    session_token = Column(String, nullable=True, unique=True)


class AgentRun(Base):
    """One run of the review workflow."""

    __tablename__ = config.AGENT_RUNS_TABLE

    run_id = Column(String, primary_key=True)
    thread_id = Column(String, nullable=False, unique=True)
    application_reference = Column(String, nullable=False, index=True)
    coordinator_id = Column(String, nullable=False)
    coordinator_request = Column(Text, nullable=False)
    status = Column(String, nullable=False)
    llm_call_count = Column(Integer, nullable=False)


class ApplicationReview(Base):
    """The review a run stores at the gate, and what its decision led to."""

    __tablename__ = config.APPLICATION_REVIEWS_TABLE

    review_id = Column(String, primary_key=True)
    run_id = Column(String, ForeignKey(f"{config.AGENT_RUNS_TABLE}.run_id"), nullable=False)
    application_reference = Column(String, nullable=False, index=True)
    technology = Column(String, nullable=False)
    urgency = Column(String, nullable=True)
    standard_document = Column(String, nullable=False)
    coordinator_request = Column(Text, nullable=False)
    status = Column(String, nullable=False)
    requirements = Column(JSON, nullable=False)
    requirements_met_count = Column(Integer, nullable=False)
    requirements_not_met_count = Column(Integer, nullable=False)
    requirements_not_documented_count = Column(Integer, nullable=False)
    network_triggers = Column(JSON, nullable=False)
    rating_stated = Column(Boolean, nullable=False)
    assessment = Column(String, nullable=False)
    decisions_open = Column(JSON, nullable=False)
    evidence = Column(JSON, nullable=False)
    disagreements = Column(JSON, nullable=False)
    network_work_likelihood = Column(Float, nullable=False)
    likelihood_band = Column(String, nullable=False)
    expected_working_days = Column(Integer, nullable=False)
    planned_working_days = Column(Integer, nullable=True)
    delay_expected = Column(Boolean, nullable=True)
    duration_text = Column(Text, nullable=False)
    review_plan_text = Column(Text, nullable=False)
    requirements_analysis_text = Column(Text, nullable=False)
    evidence_review_text = Column(Text, nullable=False)
    prediction_analysis_text = Column(Text, nullable=False)
    recommendation_text = Column(Text, nullable=False)
    recommended_decision = Column(String, nullable=False)
    installer_notice_text = Column(Text, nullable=True)
    notice_details = Column(JSON, nullable=True)
    household_notice_text = Column(Text, nullable=True)
    assessment_brief = Column(JSON, nullable=True)


class ReviewDecision(Base):
    """A Connections Engineer's decision on one review."""

    __tablename__ = config.REVIEW_DECISIONS_TABLE

    decision_id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(
        String,
        ForeignKey(f"{config.APPLICATION_REVIEWS_TABLE}.review_id"),
        nullable=False,
        unique=True,
    )
    decision = Column(String, nullable=False)
    decided_by = Column(String, nullable=False)
    decided_by_role = Column(String, nullable=False)
    decision_reason = Column(Text, nullable=False)


class LlmCall(Base):
    """One language model call a run made, and what it cost."""

    __tablename__ = config.LLM_CALLS_TABLE

    call_id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey(f"{config.AGENT_RUNS_TABLE}.run_id"), nullable=False,
                    index=True)
    agent_name = Column(String, nullable=False)
    model_name = Column(String, nullable=False)
    prompt_tokens = Column(Integer, nullable=False)
    response_tokens = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)
    latency_milliseconds = Column(Integer, nullable=False)


class ChatTurn(Base):
    """One question the chat replied to, refusals included."""

    __tablename__ = config.CHAT_TURNS_TABLE

    turn_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, index=True)
    user_role = Column(String, nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(String, nullable=False)
    application_reference = Column(String, nullable=True)
    substation_reference = Column(String, nullable=True)
    technology = Column(String, nullable=True)
    answer_text = Column(Text, nullable=False)
    source_documents = Column(Text, nullable=False)
    closest_distance = Column(Float, nullable=True)
    was_refused = Column(Boolean, nullable=False)
