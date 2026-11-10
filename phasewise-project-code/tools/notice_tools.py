"""The details the notices and the assessment brief carry, taken from the record by code."""

import pandas as pd

from config import config


def _answer(application, column_name):
    value = application.get(column_name)
    if value is None or value is pd.NA:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _refuse_other_screening(application, screening):
    application_reference = application.get(config.APPLICATION_REFERENCE_COLUMN)
    if screening.get("application_reference") != application_reference:
        raise ValueError(
            config.SCREENING_OF_ANOTHER_APPLICATION_MESSAGE.format(
                screening_reference=screening.get("application_reference"),
                application_reference=application_reference,
            )
        )


def _conditions(application, technology):
    conditions = {}
    for column_name in config.APPROVAL_CONDITION_COLUMNS.get(technology, []):
        value = _answer(application, column_name)
        if value is not None:
            conditions[column_name] = value
    return conditions


def build_approval_details(application, screening):
    """The details a connection approval shows, as each standard's section 7 sets out."""
    _refuse_other_screening(application, screening)
    technology = screening["technology"]
    details = {
        config.APPLICATION_REFERENCE_COLUMN: application.get(config.APPLICATION_REFERENCE_COLUMN),
        "standard_document": screening["standard_document"],
    }
    for column_name in config.APPROVAL_DETAIL_COLUMNS:
        details[column_name] = _answer(application, column_name)
    rating_column = config.RATING_COLUMNS[technology]
    details[rating_column] = _answer(application, rating_column)
    details.update(_conditions(application, technology))
    return details


def build_household_notice_details(application, screening):
    """The only facts a household notice may rest on."""
    _refuse_other_screening(application, screening)
    technology = screening["technology"]
    rating_column = config.RATING_COLUMNS[technology]
    details = {
        config.TECHNOLOGY_COLUMN: technology,
        rating_column: _answer(application, rating_column),
    }
    details.update(_conditions(application, technology))
    return details


def build_rework_details(application, screening, documentation_to_provide, disagreements):
    """Everything a rework request must name."""
    _refuse_other_screening(application, screening)
    to_put_right = []
    for requirement in screening["requirements"]:
        if requirement["result"] == config.REQUIREMENT_MET:
            continue
        to_put_right.append(
            {
                "requirement_name": requirement["requirement_name"],
                "requirement_sentence": requirement["requirement_sentence"],
                "result": requirement["result"],
                "form_answers": {
                    column_name: _answer(application, column_name)
                    for column_name in config.REQUIREMENT_ANSWER_COLUMNS[
                        requirement["requirement_kind"]
                    ]
                },
                "blank_answers": list(requirement["blank_answers"]),
            }
        )
    blank_rating = None
    if not screening["rating_stated"]:
        blank_rating = config.RATING_COLUMNS[screening["technology"]]
    return {
        config.APPLICATION_REFERENCE_COLUMN: application.get(config.APPLICATION_REFERENCE_COLUMN),
        "technology": screening["technology"],
        "standard_document": screening["standard_document"],
        "requirements_to_put_right": to_put_right,
        "blank_rating_answer": blank_rating,
        "documentation_to_provide": documentation_to_provide,
        "flagged_statements": list(disagreements),
    }


def build_assessment_brief(application, screening, likelihood, duration, disagreements):
    """The brief Network Planning receives with a referred application."""
    _refuse_other_screening(application, screening)
    brief = {
        config.APPLICATION_REFERENCE_COLUMN: application.get(config.APPLICATION_REFERENCE_COLUMN),
        "technology": screening["technology"],
        "standard_document": screening["standard_document"],
    }
    for column_name in config.ASSESSMENT_BRIEF_DETAIL_COLUMNS:
        brief[column_name] = _answer(application, column_name)
    brief.update(
        {
            "requirements": [
                {
                    "requirement_name": requirement["requirement_name"],
                    "result": requirement["result"],
                    "blank_answers": list(requirement["blank_answers"]),
                }
                for requirement in screening["requirements"]
            ],
            "network_triggers": list(screening["network_triggers"]),
            "flagged_statements": list(disagreements),
            "network_work_likelihood": likelihood["network_work_likelihood"],
            "likelihood_band": likelihood["likelihood_band"],
            "expected_working_days": duration["expected_working_days"],
            "planned_working_days": duration["planned_working_days"],
            "delay_expected": duration["delay_expected"],
        }
    )
    return brief
