"""The language model client, the reply parser and the seven agents.

Every agent is exactly one language model call. Each is handed facts the tools
already established and asked for prose in labelled fields; none calculates
anything of its own.
"""

import os
import re
import time
from decimal import Decimal, InvalidOperation

from dotenv import load_dotenv
from google import genai
from google.genai import types

from config import config
from tools.application_data_tools import describe_record
from tools.prediction_tools import describe_expected_working_days

load_dotenv(config.ENV_FILE)

generation_settings = types.GenerateContentConfig(
    max_output_tokens=config.GEMINI_MAX_OUTPUT_TOKENS,
    temperature=config.GEMINI_TEMPERATURE,
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
)

NONE_TEXT = "none"


# --------------------------------------------------------------------------- client


def call_language_model(prompt_text, agent_name):
    """Make one language model call and measure what it cost."""
    api_key = os.environ.get(config.GEMINI_API_KEY_VARIABLE)
    model_name = os.environ.get(config.GEMINI_MODEL_VARIABLE)
    if not api_key or not model_name:
        raise ValueError(
            f"{agent_name} cannot call the language model: set "
            f"{config.GEMINI_API_KEY_VARIABLE} and {config.GEMINI_MODEL_VARIABLE} in "
            f"{config.ENV_FILE}"
        )
    client = genai.Client(api_key=api_key)
    try:
        started = time.perf_counter()
        response = client.models.generate_content(
            model=model_name, contents=prompt_text, config=generation_settings
        )
        latency = int(round((time.perf_counter() - started) * config.MILLISECONDS_PER_SECOND))
    finally:
        closer = getattr(client, "close", None)
        if callable(closer):
            closer()
    candidates = response.candidates or []
    finish_reason = candidates[0].finish_reason if candidates else None
    if finish_reason != types.FinishReason.STOP:
        raise ValueError(
            f"{agent_name}'s reply from {model_name} did not finish normally ({finish_reason})"
        )
    response_text = (response.text or "").strip()
    if not response_text:
        raise ValueError(f"{agent_name}'s reply from {model_name} is empty")
    usage = response.usage_metadata
    counts = [
        getattr(usage, "prompt_token_count", None),
        getattr(usage, "candidates_token_count", None),
        getattr(usage, "total_token_count", None),
    ]
    if usage is None or any(count is None for count in counts):
        raise ValueError(
            f"{agent_name}'s reply from {model_name} does not say how many tokens it used"
        )
    return {
        "response_text": response_text,
        "call_record": {
            "agent_name": agent_name,
            "model_name": model_name,
            "prompt_tokens": int(counts[0]),
            "response_tokens": int(counts[1]),
            "total_tokens": int(counts[2]),
            "latency_milliseconds": latency,
        },
    }


# --------------------------------------------------------------------------- replies


def _label_of(text_before_colon):
    bare = re.sub(config.RESPONSE_DECORATION_EDGE_PATTERN, "", text_before_colon.strip())
    bare = bare.replace("-", " ")
    return re.sub(r"\s+", " ", bare).strip().upper()


def parse_labelled_response(response_text, field_labels, agent_name):
    """Read a labelled reply back into exactly the fields asked for."""
    wanted = [label.upper() for label in field_labels]
    fields = {label: [] for label in wanted}
    current = None
    for raw_line in response_text.splitlines():
        line = raw_line.replace("**", "").strip()
        if ":" in line:
            before, after = line.split(":", 1)
            label = _label_of(before)
            if label in fields:
                current = label
                value = after.strip(config.RESPONSE_DECORATION_CHARACTERS)
                if value:
                    fields[current].append(value)
                continue
        if current is None:
            continue
        if not re.sub(config.RESPONSE_DECORATION_EDGE_PATTERN, "", line):
            continue
        fields[current].append(line)
    empty = [label for label in wanted if not "\n".join(fields[label]).strip()]
    if empty:
        raise ValueError(
            f"{agent_name}'s reply leaves out or leaves empty: " + ", ".join(empty)
        )
    return {
        original: "\n".join(fields[original.upper()]).strip() for original in field_labels
    }


def join_labelled_response(labelled_fields):
    """An agent's fields written back as one text for the record."""
    return "\n\n".join(f"{label}: {text}" for label, text in labelled_fields.items())


def _reply_layout(field_labels):
    lines = "\n".join(f"{label}: <your text>" for label in field_labels)
    return (
        "Reply with exactly these labelled fields, in this order, each label at the start of its "
        "own line followed by a colon. Write at least two full sentences in every field unless a "
        "field asks for a single value, write 'None.' in a field when nothing belongs in it, and "
        "never start any other line with one of these labels:\n" + lines
    )


def _one_line(value, field, agent_name):
    if "\n" in value.strip():
        raise ValueError(f"{agent_name} wrote {field} over more than one line")
    return value.strip()


def _bare_upper(value):
    return re.sub(config.RESPONSE_DECORATION_EDGE_PATTERN, "", value.strip()).upper()


# --------------------------------------------------------------------------- wording


def _technology_words(technology):
    return f"{config.TECHNOLOGY_NAMES.get(technology, technology)} ({technology})"


def _label(column_name):
    return config.FORM_ANSWER_LABELS.get(column_name, column_name.replace("_", " "))


def _answers_block(application, columns):
    described = describe_record({column: application.get(column) for column in columns})
    return "\n".join(f"- {_label(column)}: {described[column]}" for column in columns)


def _list_or_none(lines):
    return "\n".join(lines) if lines else NONE_TEXT


def _amps_text(values):
    return ", ".join(f"{float(value):.{config.AMPS_DECIMALS}f}" for value in values) or NONE_TEXT


def _requirements_lines(screening, application=None, with_answers=False):
    lines = []
    for requirement in screening["requirements"]:
        line = (
            f"- {requirement['requirement_name']}: {requirement['result']}. Sentence: "
            f"\"{requirement['requirement_sentence']}\""
        )
        if requirement["blank_answers"]:
            line += " Blank answers: " + ", ".join(
                _label(column) for column in requirement["blank_answers"]
            ) + "."
        if with_answers and application is not None:
            columns = config.REQUIREMENT_ANSWER_COLUMNS[requirement["requirement_kind"]]
            described = describe_record({column: application.get(column) for column in columns})
            line += " Answers read: " + "; ".join(
                f"{_label(column)} = {described[column]}" for column in columns
            ) + "."
        lines.append(line)
    return _list_or_none(lines)


def _counts_text(screening):
    return (
        f"Met {screening[config.REQUIREMENTS_MET_COUNT_COLUMN]}, Not met "
        f"{screening[config.REQUIREMENTS_NOT_MET_COUNT_COLUMN]}, Not documented "
        f"{screening[config.REQUIREMENTS_NOT_DOCUMENTED_COUNT_COLUMN]}; rating stated: "
        f"{config.BOOLEAN_YES if screening['rating_stated'] else config.BOOLEAN_NO}"
    )


def _screening_summary(screening):
    return (
        f"Standard screened under: {screening['standard_document']}\n"
        f"Requirements:\n{_requirements_lines(screening)}\n"
        f"Counts: {_counts_text(screening)}\n"
        f"Network triggers: {', '.join(screening['network_triggers']) or NONE_TEXT}\n"
        f"Assessment: {screening['assessment']}\n"
        f"Decisions open: {', '.join(screening['decisions_open'])}"
    )


def _opening(role_text):
    return (
        f"You are the {role_text} for {config.ORGANISATION_NAME}, reviewing a home low-carbon "
        "connection application. Every fact below was established by the connection standards, "
        "the models and the tools. Use only these facts. Do not alter any result, do not work "
        "anything out yourself and do not introduce any figure that is not written below.\n\n"
    )


# --------------------------------------------------------------------------- reviewing agents


def plan_review(application_profile, application_documents, screening, coordinator_request):
    """Decide what the review has to establish about this application."""
    profile = describe_record(application_profile)
    technology = application_profile.get(config.TECHNOLOGY_COLUMN)
    statements = [
        f"- {document.get(config.DOCUMENT_ID_COLUMN)}: {document.get(config.DOCUMENT_TITLE_COLUMN)}"
        for document in application_documents
    ]
    prompt = (
        _opening("review planner")
        + "APPLICATION\n"
        f"- Reference: {profile[config.APPLICATION_REFERENCE_COLUMN]}\n"
        f"- Portal: {profile[config.SOURCE_PORTAL_COLUMN]}\n"
        f"- Revision: {profile[config.REVISION_NUMBER_COLUMN]}\n"
        f"- Technology: {_technology_words(technology)}\n"
        f"- Premises type: {profile[config.PREMISES_TYPE_COLUMN]}\n"
        f"- Region type: {profile[config.REGION_TYPE_COLUMN]}\n"
        f"- Substation: {profile[config.SUBSTATION_REFERENCE_COLUMN]}\n"
        f"- Urgency: {profile[config.URGENCY_COLUMN]}\n"
        f"- Supply phases: {profile[config.SUPPLY_PHASES_COLUMN]}\n"
        f"- Equipment phases: {profile[config.EQUIPMENT_PHASES_COLUMN]}\n"
        f"- Service type: {profile[config.SERVICE_TYPE_COLUMN]}\n"
        f"- Cut-out rating, in amps: {profile[config.CUT_OUT_RATING_COLUMN]}\n\n"
        "STATEMENTS ATTACHED\n"
        + (_list_or_none(statements) if statements else "No statement is attached.")
        + "\n\nSCREENING\n" + _screening_summary(screening) + "\n\n"
        f"WHAT THE PERSON WHO OPENED THE REVIEW ASKED\n{coordinator_request}\n\n"
        "TASK\nPlan the review: say which requirement or trigger deserves attention first, which "
        "checks the review must make against the form and the statements, and why.\n\n"
        + _reply_layout(["PRIORITY", "CHECKS", "RATIONALE"])
    )
    reply = call_language_model(prompt, config.AGENT_NAME_PLANNER)
    plan = parse_labelled_response(
        reply["response_text"], ["PRIORITY", "CHECKS", "RATIONALE"], config.AGENT_NAME_PLANNER
    )
    return {"review_plan": plan, "call_record": reply["call_record"]}


def analyse_requirements(screening, application_profile, review_plan):
    """Account for each requirement's result and for the network triggers."""
    labels = [
        "REQUIREMENTS MET",
        "REQUIREMENTS NOT MET",
        "NOT DOCUMENTED",
        "NETWORK TRIGGERS",
        "REQUIREMENTS SUMMARY",
    ]
    prompt = (
        _opening("requirements analyst")
        + f"STANDARD: {screening['standard_document']}\n\n"
        "REQUIREMENTS, IN THE STANDARD'S ORDER\n"
        + _requirements_lines(screening, application_profile, with_answers=True)
        + f"\n\nCOUNTS\n{_counts_text(screening)}\n{config.CURRENT_RULE_TEXT}\n\n"
        "ANSWERS THE NETWORK TRIGGERS READ\n"
        + _answers_block(application_profile, config.TRIGGER_ANSWER_COLUMNS)
        + f"\nTriggers that apply: {', '.join(screening['network_triggers']) or NONE_TEXT}\n"
        f"{config.NETWORK_BLANK_ANSWER_RULE_TEXT}\n\n"
        f"ASSESSMENT: {screening['assessment']}\n{config.ASSESSMENT_RULE_TEXT}\n"
        f"Decisions open: {', '.join(screening['decisions_open'])}\n\n"
        f"THE PLAN'S CHECKS\n{review_plan['CHECKS']}\n\n"
        "TASK\nExplain each result exactly as the screening gave it, in words a Connections "
        "Engineer can check against the form. Never supply a blank answer from a statement, and "
        "never present the application as already decided.\n\n"
        + _reply_layout(labels)
    )
    reply = call_language_model(prompt, config.AGENT_NAME_REQUIREMENTS)
    analysis = parse_labelled_response(
        reply["response_text"], labels, config.AGENT_NAME_REQUIREMENTS
    )
    return {"requirements_analysis": analysis, "call_record": reply["call_record"]}


def review_evidence(evidence_findings, disagreements, reviewer_checks, application_profile,
                    screening, review_plan):
    """Set the evidence in the statements beside the form."""
    labels = ["EVIDENCE FOUND", "DISAGREEMENTS", "CHECKS TO MAKE", "EVIDENCE SUMMARY"]
    columns = []
    for requirement in screening["requirements"]:
        for column in config.REQUIREMENT_ANSWER_COLUMNS[requirement["requirement_kind"]]:
            if column not in columns:
                columns.append(column)
    for column in config.STATEMENT_GUIDE_ANSWER_COLUMNS:
        if column not in columns:
            columns.append(column)
    sentence_lines = []
    current_document = None
    for finding in evidence_findings:
        if finding["document_id"] != current_document:
            current_document = finding["document_id"]
            sentence_lines.append(f"Statement {current_document} ({finding['document_type']}):")
        borne = ", ".join(finding.get("requirements_borne_on", [])) or NONE_TEXT
        sentence_lines.append(
            f"- [{finding['sentence_type']}] {finding['sentence']} (bears on: {borne})"
        )
    flag_lines = [
        f"- {flag['document_id']}: \"{flag['sentence']}\" states {_amps_text(flag['stated_amps'])} "
        f"amps per phase; the form's ratings are {_amps_text(flag['form_rating_amps'])} amps per "
        f"phase; flag {flag['flag']}"
        for flag in disagreements
    ]
    check_lines = [
        f"- {sentence_type}, from {config.SENTENCE_TYPE_GUIDE_DOCUMENTS[sentence_type]}: {checks}"
        for sentence_type, checks in reviewer_checks.items()
    ]
    prompt = (
        _opening("evidence analyst")
        + "FORM ANSWERS\n" + _answers_block(application_profile, columns) + "\n\n"
        "SENTENCES READ, STATEMENT BY STATEMENT\n" + _list_or_none(sentence_lines) + "\n\n"
        "FLAGGED SENTENCES\n" + _list_or_none(flag_lines) + "\n\n"
        "WHAT THE STATEMENT GUIDES SAY THE REVIEWER CHECKS\n" + _list_or_none(check_lines) + "\n\n"
        f"THE PLAN'S CHECKS\n{review_plan['CHECKS']}\n\n"
        "TASK\nThe statements are evidence only and never a substitute for an answer on the form. "
        "A flagged disagreement is left for the Connections Engineer to settle.\n\n"
        + _reply_layout(labels)
    )
    reply = call_language_model(prompt, config.AGENT_NAME_EVIDENCE)
    review = parse_labelled_response(reply["response_text"], labels, config.AGENT_NAME_EVIDENCE)
    return {"evidence_review": review, "call_record": reply["call_record"]}


def analyse_predictions(likelihood, duration, application_profile, screening, review_plan):
    """Interpret the network work likelihood and the expected working days."""
    labels = ["LIKELIHOOD", "EXPECTED WORKING DAYS", "PREDICTION SUMMARY"]
    work_inputs = dict(application_profile)
    for column in config.REQUIREMENT_COUNT_RESULTS:
        work_inputs[column] = screening[column]
    for trigger, column in config.NETWORK_TRIGGER_FLAG_COLUMNS.items():
        work_inputs[column] = int(trigger in screening["network_triggers"])
    work_columns = config.NETWORK_WORK_NUMERIC_FEATURES + config.NETWORK_WORK_CATEGORICAL_FEATURES
    days_columns = config.DURATION_NUMERIC_FEATURES + config.DURATION_CATEGORICAL_FEATURES
    prompt = (
        _opening("risk analyst")
        + "NETWORK WORK LIKELIHOOD\n"
        f"- Figure: {likelihood['network_work_likelihood']:.{config.LIKELIHOOD_DECIMALS}f}, band "
        f"{likelihood['likelihood_band']}\n"
        f"- Bands: {config.HIGH_LIKELIHOOD_BAND} from {config.HIGH_LIKELIHOOD_MINIMUM}, "
        f"{config.MEDIUM_LIKELIHOOD_BAND} from {config.MEDIUM_LIKELIHOOD_MINIMUM}, otherwise "
        f"{config.LOW_LIKELIHOOD_BAND}\n"
        "Inputs of the network work model:\n" + _answers_block(work_inputs, work_columns) + "\n\n"
        "EXPECTED WORKING DAYS\n"
        f"- {describe_expected_working_days(duration)} (a delay is expected only beyond "
        f"{config.DELAY_MARGIN_WORKING_DAYS} working days over the plan)\n"
        "Inputs of the duration model:\n" + _answers_block(work_inputs, days_columns) + "\n"
        f"{config.BLANK_INPUT_RULE_TEXT}\n\n"
        f"THE PLAN'S CHECKS\n{review_plan['CHECKS']}\n\n"
        "TASK\nExplain what each figure means and which inputs stand behind it. Neither figure "
        "has any bearing on a requirement, a network trigger, a decision or a notice, and you "
        "must not recalculate either.\n\n"
        + _reply_layout(labels)
    )
    reply = call_language_model(prompt, config.AGENT_NAME_RISK)
    analysis = parse_labelled_response(reply["response_text"], labels, config.AGENT_NAME_RISK)
    return {"prediction_analysis": analysis, "call_record": reply["call_record"]}


def write_review_recommendation(application_profile, coordinator_request, screening,
                                likelihood, duration, review_plan, requirements_analysis,
                                evidence_review, prediction_analysis):
    """Write the review a Connections Engineer decides from, recommending an open decision."""
    labels = ["RECOMMENDATION", "RECOMMENDED DECISION"]
    profile = describe_record(application_profile)
    technology = application_profile.get(config.TECHNOLOGY_COLUMN)
    decisions = "\n".join(
        f"- {decision}: {config.DECISION_DESCRIPTIONS[decision]} "
        f"{config.DECISION_OPEN_CONDITIONS[decision]}"
        for decision in config.DECISIONS
    )
    analyst_fields = "\n".join(
        f"{label}: {text}"
        for fields in [requirements_analysis, evidence_review, prediction_analysis]
        for label, text in fields.items()
    )
    prompt = (
        _opening("review writer")
        + f"APPLICATION {profile[config.APPLICATION_REFERENCE_COLUMN]}, "
        f"{_technology_words(technology)}, urgency {profile[config.URGENCY_COLUMN]}, standard "
        f"{screening['standard_document']}\n"
        f"Request: {coordinator_request}\n\n"
        f"PLAN\nPRIORITY: {review_plan['PRIORITY']}\nCHECKS: {review_plan['CHECKS']}\n\n"
        f"ANALYSTS\n{analyst_fields}\n\n"
        "SCREENING\n" + _screening_summary(screening) + "\n"
        f"{config.ASSESSMENT_RULE_TEXT}\n\n"
        f"FIGURES (never a reason for a decision)\n- Network work likelihood "
        f"{likelihood['network_work_likelihood']:.{config.LIKELIHOOD_DECIMALS}f}, band "
        f"{likelihood['likelihood_band']}\n- {describe_expected_working_days(duration)}\n\n"
        f"THE DECISIONS\n{decisions}\nDecisions open: {', '.join(screening['decisions_open'])}\n\n"
        "TASK\nYou only recommend; a Connections Engineer decides. Recommend the assessment, "
        f"{screening['assessment']}, unless the review supports another open decision, and then "
        "give that reason. Never cite either figure as a reason. RECOMMENDATION is several "
        "sentences of prose whose last sentence names the decision you recommend and why. "
        "RECOMMENDED DECISION is exactly one of the decisions open, on one line, and nothing "
        "else.\n\n"
        + _reply_layout(labels)
    )
    reply = call_language_model(prompt, config.AGENT_NAME_WRITER)
    fields = parse_labelled_response(reply["response_text"], labels, config.AGENT_NAME_WRITER)
    decision = _bare_upper(
        _one_line(fields["RECOMMENDED DECISION"], "RECOMMENDED DECISION", config.AGENT_NAME_WRITER)
    )
    if decision not in screening["decisions_open"]:
        raise ValueError(
            f"{config.AGENT_NAME_WRITER} recommended {decision}, which is not among the "
            f"decisions open: {', '.join(screening['decisions_open'])}"
        )
    fields["RECOMMENDED DECISION"] = decision
    return {"review_recommendation": fields, "call_record": reply["call_record"]}


# --------------------------------------------------------------------------- notice checks


def _flat(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def _figures(text):
    found = []
    for figure in re.findall(config.FIGURE_PATTERN, text.replace(config.THOUSANDS_SEPARATOR, "")):
        try:
            found.append(Decimal(figure))
        except InvalidOperation:
            continue
    return found


def _gives_figure(text, value):
    wanted = Decimal(repr(float(value))) if not isinstance(value, int) else Decimal(value)
    return any(figure == wanted for figure in _figures(text))


def _names_technology(flat_text, technology):
    name = config.TECHNOLOGY_NAMES.get(technology, technology).lower()
    return name in flat_text or re.search(rf"\b{re.escape(technology.lower())}\b", flat_text)


def _check_sign_off_and_slots(notice, agent_name):
    if any(character in notice for character in config.TEMPLATE_SLOT_CHARACTERS):
        raise ValueError(f"{agent_name} left a gap to fill in its notice")

    def spaced(text):
        return re.sub(config.SIGN_OFF_SPACING_PATTERN, " ", text.lower()).strip()

    if not spaced(notice).endswith(spaced(config.NOTICE_SIGN_OFF)):
        raise ValueError(f"{agent_name}'s notice does not end with {config.NOTICE_SIGN_OFF}")


def _check_forbidden_terms(flat_text, agent_name):
    used = [term for term in config.NOTICE_FORBIDDEN_TERMS if term.lower() in flat_text]
    if used:
        raise ValueError(f"{agent_name}'s notice speaks of " + ", ".join(used))


def _value_words(value):
    return describe_record({"value": value})["value"]


# --------------------------------------------------------------------------- notice agents


def draft_installer_notice(decision, application_profile, notice_details, notice_guidance):
    """Write the connection approval or the rework request to the installer."""
    agent_name = config.AGENT_NAME_INSTALLER_NOTICE
    labels = ["SUBJECT", "NOTICE"]
    technology = notice_details.get(config.TECHNOLOGY_COLUMN) or application_profile.get(
        config.TECHNOLOGY_COLUMN
    )
    rating_column = config.RATING_COLUMNS[technology]
    reference = notice_details.get(config.APPLICATION_REFERENCE_COLUMN)
    kind = config.NOTICE_KINDS[decision]
    tech_words = _technology_words(technology)
    if decision == config.DECISION_APPROVE:
        if notice_details.get(rating_column) is None:
            raise ValueError(f"{agent_name} cannot write an approval whose details give no rating")
        described = describe_record(notice_details)
        detail_lines = []
        for key in notice_details:
            label = config.NOTICE_DETAIL_LABELS.get(key, _label(key))
            value = tech_words if key == config.TECHNOLOGY_COLUMN else described[key]
            detail_lines.append(f"- {label}: {value}")
        required = (
            f"The {config.TECHNOLOGY_NAMES[technology]} for application {reference} is approved "
            f"with a {config.RATING_TERMS[rating_column]} of {described[rating_column]}"
            + (" amps per phase." if rating_column == config.RATED_CURRENT_COLUMN else " kW.")
        )
        details_text = "\n".join(detail_lines)
        must_name = []
    else:
        described = describe_record(
            {
                config.APPLICATION_REFERENCE_COLUMN: reference,
                config.TECHNOLOGY_COLUMN: notice_details["technology"],
                "standard_document": notice_details["standard_document"],
            }
        )
        lines = [
            f"- {config.NOTICE_DETAIL_LABELS[config.APPLICATION_REFERENCE_COLUMN]}: "
            f"{described[config.APPLICATION_REFERENCE_COLUMN]}",
            f"- {config.NOTICE_DETAIL_LABELS[config.TECHNOLOGY_COLUMN]}: {tech_words}",
            f"- {config.NOTICE_DETAIL_LABELS['standard_document']}: "
            f"{described['standard_document']}",
            "Requirements to put right:",
        ]
        must_name = []
        for requirement in notice_details["requirements_to_put_right"]:
            must_name.append(requirement["requirement_name"])
            answers = describe_record(requirement["form_answers"])
            lines.append(
                f"- {requirement['requirement_name']} ({requirement['result']}): "
                f"\"{requirement['requirement_sentence']}\" Form answers: "
                + "; ".join(f"{_label(column)} = {text}" for column, text in answers.items())
                + ". Answers needed: "
                + (", ".join(_label(column) for column in requirement["blank_answers"])
                   or NONE_TEXT)
            )
        if not notice_details["requirements_to_put_right"]:
            lines.append(f"- {NONE_TEXT}")
        blank_rating = notice_details.get("blank_rating_answer")
        if blank_rating:
            must_name.append(config.RATING_TERMS[blank_rating])
            lines.append(
                f"The form leaves the {config.RATING_TERMS[blank_rating]} blank, and every "
                "application states its equipment's rating."
            )
        lines.append(
            "Documentation to provide: " + str(notice_details.get("documentation_to_provide"))
        )
        flags = notice_details.get("flagged_statements") or []
        lines.append("Statement sentences flagged against the form:")
        lines.append(
            _list_or_none(
                [
                    f"- {flag['document_id']}: \"{flag['sentence']}\" states "
                    f"{_amps_text(flag['stated_amps'])} amps per phase against the form's "
                    f"{_amps_text(flag['form_rating_amps'])}"
                    for flag in flags
                ]
            )
        )
        details_text = "\n".join(lines)
        required = (
            "Name each of these word for word in the notice: " + "; ".join(must_name) + "."
            if must_name
            else ""
        )
    prompt = (
        f"You write the {kind} to an installer for {config.ORGANISATION_NAME}.\n\n"
        f"DECISION: {decision}: {config.DECISION_DESCRIPTIONS[decision]}\n"
        f"The installer applied through {application_profile.get(config.SOURCE_PORTAL_COLUMN)}.\n\n"
        f"DETAILS\n{details_text}\n\n"
        f"GUIDANCE\n{notice_guidance}\n\n"
        "RULES\n"
        f"- The SUBJECT is one line and names the application reference {reference}.\n"
        f"- Name the technology, the {config.TECHNOLOGY_NAMES[technology]}, in the notice.\n"
        + (f"- {required}\n" if required else "")
        + "- Use only the details above. Do not mention any model figure, any likelihood, "
        "probability or expected working days, the name of anyone at the organisation, or any "
        "made-up time, date or contact detail.\n"
        "- Never use square brackets and never leave a gap to fill in.\n"
        f"- The NOTICE ends with this exact line: {config.NOTICE_SIGN_OFF}\n\n"
        + _reply_layout(labels)
    )
    reply = call_language_model(prompt, agent_name)
    fields = parse_labelled_response(reply["response_text"], labels, agent_name)
    subject = _one_line(fields["SUBJECT"], "SUBJECT", agent_name)
    if str(reference).lower() not in subject.lower():
        raise ValueError(f"{agent_name}'s subject does not name {reference}")
    flat_text = _flat(subject + " " + fields["NOTICE"])
    if decision == config.DECISION_APPROVE:
        if not _names_technology(flat_text, technology):
            raise ValueError(f"{agent_name}'s approval does not name the technology")
        if not _gives_figure(flat_text, notice_details[rating_column]):
            raise ValueError(f"{agent_name}'s approval does not give the rating as a figure")
    else:
        missing = [name for name in must_name if name.lower() not in flat_text]
        if missing:
            raise ValueError(f"{agent_name}'s rework request does not name " + ", ".join(missing))
    _check_forbidden_terms(flat_text, agent_name)
    _check_sign_off_and_slots(fields["NOTICE"], agent_name)
    fields["SUBJECT"] = subject
    return {"installer_notice": fields, "call_record": reply["call_record"]}


def draft_household_notice(application_profile, household_details, household_guidance):
    """Write the household notice to the people who live at the premises."""
    agent_name = config.AGENT_NAME_HOUSEHOLD_NOTICE
    labels = ["HEADLINE", "NOTICE"]
    technology = household_details[config.TECHNOLOGY_COLUMN]
    rating_column = config.RATING_COLUMNS[technology]
    if household_details.get(rating_column) is None:
        raise ValueError(f"{agent_name} cannot write a household notice that gives no rating")
    described = describe_record(household_details)
    equipment = config.EQUIPMENT_NAMES[technology]
    conditions = [
        column
        for column in config.APPROVAL_CONDITION_COLUMNS.get(technology, [])
        if household_details.get(column) is not None
    ]
    condition_lines = [
        config.HOUSEHOLD_CONDITION_TEMPLATES[column].format(
            equipment_name=equipment, value=described[column]
        )
        for column in conditions
    ]
    prompt = (
        f"You write a short, friendly household notice for {config.ORGANISATION_NAME} to the "
        "people who live at a home whose low-carbon connection has been approved.\n\n"
        f"TECHNOLOGY: {config.TECHNOLOGY_NAMES[technology]}\n"
        f"{config.NOTICE_DETAIL_LABELS[rating_column]}: {described[rating_column]}\n"
        "CONDITIONS THE HOUSEHOLD MUST KEEP TO:\n"
        + (_list_or_none([f"- {line}" for line in condition_lines]) if condition_lines
           else "There is neither an export limit nor a load limiting setting.")
        + f"\n\nGUIDANCE\n{household_guidance}\n\n"
        "RULES\n"
        f"- Name the technology, the {config.TECHNOLOGY_NAMES[technology]}, in the notice.\n"
        + "".join(f"- Include this sentence word for word: {line}\n" for line in condition_lines)
        + "- Never mention the substation, the cut-out or its rating, or the maximum demand, "
        "even if the guidance does.\n"
        "- Do not mention any model figure, any likelihood, probability or expected working "
        "days, the name of anyone at the organisation, or any made-up time, date or contact "
        "detail.\n"
        "- Never use square brackets and never leave a gap to fill in.\n"
        "- The HEADLINE is one line.\n"
        f"- The NOTICE ends with this exact line: {config.NOTICE_SIGN_OFF}\n\n"
        + _reply_layout(labels)
    )
    reply = call_language_model(prompt, agent_name)
    fields = parse_labelled_response(reply["response_text"], labels, agent_name)
    headline = _one_line(fields["HEADLINE"], "HEADLINE", agent_name)
    flat_text = _flat(headline + " " + fields["NOTICE"])
    if not _names_technology(flat_text, technology):
        raise ValueError(f"{agent_name}'s notice does not name the technology")
    for column in conditions:
        if not _gives_figure(flat_text, household_details[column]):
            raise ValueError(f"{agent_name}'s notice does not give {_label(column)} as a figure")
    withheld = [
        name for name, pattern in config.HOUSEHOLD_NOTICE_WITHHELD_PATTERNS.items()
        if re.search(pattern, flat_text)
    ]
    if withheld:
        raise ValueError(f"{agent_name}'s notice names " + ", ".join(withheld))
    _check_forbidden_terms(flat_text, agent_name)
    for account in config.SEED_USER_ACCOUNTS:
        if re.search(rf"\b{re.escape(account['username'].lower())}\b", flat_text) or (
            account["display_name"].lower() in flat_text
        ):
            raise ValueError(f"{agent_name}'s notice names a member of staff")
    _check_sign_off_and_slots(fields["NOTICE"], agent_name)
    fields["HEADLINE"] = headline
    return {"household_notice": fields, "call_record": reply["call_record"]}
