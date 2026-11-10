"""Every read and write against the six tables. Reads return plain records."""

from sqlalchemy import select

from persistence.models import (
    AgentRun,
    ApplicationReview,
    ChatTurn,
    LlmCall,
    ReviewDecision,
    UserAccount,
)


def _record(row, model):
    return {column.name: getattr(row, column.name) for column in model.__table__.columns}


def insert_user_account(session, account_record):
    """Create one sign-in account in the caller's transaction."""
    session.add(UserAccount(**account_record))
    session.flush()


def fetch_user_account(session, condition):
    """One account as a plain record, or None."""
    row = session.execute(select(UserAccount).where(condition)).scalars().first()
    return None if row is None else _record(row, UserAccount)


def update_session_token(session, username, session_token):
    """Start or end one person's session."""
    row = session.get(UserAccount, username)
    if row is None:
        raise ValueError(f"No account has the username {username}")
    row.session_token = session_token
    session.flush()


def insert_agent_run(session, run_record):
    """Open the record of one workflow run."""
    session.add(AgentRun(**run_record))
    session.flush()


def fetch_agent_run(session, condition):
    """One run as a plain record, or None."""
    row = session.execute(select(AgentRun).where(condition)).scalars().first()
    return None if row is None else _record(row, AgentRun)


def update_agent_run(session, run_id, status_value, llm_call_count):
    """Move a run on, recording what it has cost."""
    row = session.get(AgentRun, run_id)
    if row is None:
        raise ValueError(f"No agent run has the identifier {run_id}")
    row.status = status_value
    row.llm_call_count = int(llm_call_count)
    session.flush()


def insert_llm_call(session, run_id, call_record):
    """Record one language model call against its run."""
    session.add(LlmCall(run_id=run_id, **call_record))
    session.flush()


def fetch_llm_calls(session, run_id):
    """A run's calls, in the order they were made."""
    rows = session.execute(
        select(LlmCall).where(LlmCall.run_id == run_id).order_by(LlmCall.call_id)
    ).scalars()
    return [
        {
            "agent_name": row.agent_name,
            "model_name": row.model_name,
            "prompt_tokens": row.prompt_tokens,
            "response_tokens": row.response_tokens,
            "total_tokens": row.total_tokens,
            "latency_milliseconds": row.latency_milliseconds,
        }
        for row in rows
    ]


def insert_application_review(session, review_record):
    """Store the review waiting at the gate."""
    session.add(ApplicationReview(**review_record))
    session.flush()


def fetch_review_records(session, condition):
    """Reviews with their run and their decision, by application reference then identifier."""
    rows = session.execute(
        select(ApplicationReview, AgentRun, ReviewDecision)
        .outerjoin(AgentRun, AgentRun.run_id == ApplicationReview.run_id)
        .outerjoin(ReviewDecision, ReviewDecision.review_id == ApplicationReview.review_id)
        .where(condition)
        .order_by(ApplicationReview.application_reference, ApplicationReview.review_id)
    ).all()
    records = []
    for review, run, decision in rows:
        record = _record(review, ApplicationReview)
        record["thread_id"] = None if run is None else run.thread_id
        record["coordinator_id"] = None if run is None else run.coordinator_id
        record["llm_call_count"] = None if run is None else run.llm_call_count
        for field in ["decision", "decided_by", "decided_by_role", "decision_reason"]:
            record[field] = None if decision is None else getattr(decision, field)
        records.append(record)
    return records


def insert_review_decision(session, decision_record):
    """Record a Connections Engineer's decision, one per review."""
    session.add(ReviewDecision(**decision_record))
    session.flush()


def record_review_outcome(session, review_id, outcome_record):
    """Write exactly the given columns onto a decided review."""
    row = session.get(ApplicationReview, review_id)
    if row is None:
        raise ValueError(f"No application review has the identifier {review_id}")
    for column_name, value in outcome_record.items():
        setattr(row, column_name, value)
    session.flush()


def insert_chat_turn(session, turn_record):
    """Record one chat exchange, refusals included."""
    session.add(ChatTurn(**turn_record))
    session.flush()


def fetch_chat_turns(session, condition, turn_limit):
    """The most recent chat turns meeting the condition, newest first."""
    rows = session.execute(
        select(ChatTurn).where(condition).order_by(ChatTurn.turn_id.desc()).limit(int(turn_limit))
    ).scalars()
    return [_record(row, ChatTurn) for row in rows]
