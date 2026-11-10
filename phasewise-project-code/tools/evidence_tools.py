"""Reads every sentence of an application's statements, links it and flags disagreements."""

import re
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from config import config
from data_pipeline.common_cleaning import convert_power_to_amps_per_phase


def _is_blank(value):
    if value is None or value is pd.NA:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def read_document_evidence(sentence_model, documents):
    """One finding per sentence, statement by statement, in the order written."""
    pieces = []
    for document in documents:
        document_id = document[config.DOCUMENT_ID_COLUMN]
        text = document.get(config.DOCUMENT_TEXT_COLUMN)
        if _is_blank(text) or not str(text).strip():
            raise ValueError(config.NO_STATEMENT_TEXT_MESSAGE.format(document_id=document_id))
        for sentence in re.split(config.STATEMENT_SENTENCE_PATTERN, str(text)):
            if sentence:
                pieces.append((document, sentence))
    if not pieces:
        return []
    predicted = sentence_model.predict([sentence for _, sentence in pieces])
    findings = []
    for (document, sentence), sentence_type in zip(pieces, predicted):
        findings.append(
            {
                "document_id": document[config.DOCUMENT_ID_COLUMN],
                "document_type": document.get(config.DOCUMENT_TYPE_COLUMN),
                "sentence": sentence,
                "sentence_type": str(sentence_type),
            }
        )
    return findings


def link_evidence_to_requirements(findings, screening):
    """Record which requirements of the application's own standard each sentence bears on."""
    linked = []
    for finding in findings:
        sentence_type = finding["sentence_type"]
        if sentence_type not in config.SENTENCE_TYPE_REQUIREMENT_KINDS:
            raise ValueError(
                config.NO_REQUIREMENT_KINDS_MESSAGE.format(sentence_type=sentence_type)
            )
        kinds = config.SENTENCE_TYPE_REQUIREMENT_KINDS[sentence_type]
        borne_on = [
            requirement["requirement_name"]
            for requirement in screening["requirements"]
            if requirement["requirement_kind"] in kinds
        ]
        linked.append(dict(finding, requirements_borne_on=borne_on))
    return linked


def _form_rating_amps(application):
    phases = application.get(config.EQUIPMENT_PHASES_COLUMN)
    ratings = []
    for column_name in config.FORM_CURRENT_RATING_COLUMNS:
        value = application.get(column_name)
        if not _is_blank(value):
            ratings.append(
                Decimal(repr(float(value))).quantize(config.AMPS_STEP, rounding=ROUND_HALF_UP)
            )
    for column_name in config.FORM_POWER_RATING_COLUMNS:
        value = application.get(column_name)
        if not _is_blank(value) and not _is_blank(phases):
            ratings.append(
                convert_power_to_amps_per_phase(Decimal(repr(float(value))), int(phases))
            )
    return ratings


def _stated_amps(sentence, phases):
    stated = []
    for match in re.finditer(config.STATED_FIGURE_PATTERN, sentence):
        following = re.findall(config.FOLLOWING_WORD_PATTERN, sentence[match.end():].lower())
        if any(
            word in config.UNREAD_FIGURE_WORDS
            for word in following[:config.FOLLOWING_WORDS_CHECKED]
        ):
            continue
        number = Decimal(
            match.group(config.STATED_NUMBER_PART).replace(config.THOUSANDS_SEPARATOR, "")
        )
        unit = match.group(config.STATED_UNIT_PART).lower()
        if unit in config.STATED_CURRENT_UNITS:
            stated.append(number.quantize(config.AMPS_STEP, rounding=ROUND_HALF_UP))
            continue
        if _is_blank(phases):
            continue
        stated.append(
            convert_power_to_amps_per_phase(number * config.STATED_POWER_UNITS[unit], int(phases))
        )
    return stated


def find_disagreements(findings, application):
    """Flag every equipment rating sentence whose figures are none of the form's ratings."""
    phases = application.get(config.EQUIPMENT_PHASES_COLUMN)
    form_ratings = _form_rating_amps(application)
    flags = []
    for finding in findings:
        if finding.get("sentence_type") != config.EQUIPMENT_RATING:
            continue
        stated = _stated_amps(finding["sentence"], phases)
        if not stated:
            continue
        if not form_ratings:
            flag = config.DESCRIBES_BLANK_ANSWER
        elif not any(amps in form_ratings for amps in stated):
            flag = config.DISAGREES_WITH_FORM
        else:
            continue
        flags.append(
            {
                "document_id": finding["document_id"],
                "sentence": finding["sentence"],
                "stated_amps": [float(amps) for amps in stated],
                "form_rating_amps": [float(amps) for amps in form_ratings],
                "flag": flag,
            }
        )
    return flags
