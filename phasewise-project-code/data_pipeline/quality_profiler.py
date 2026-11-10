"""Measures how dirty each raw extract was, and writes the evidence out.

Every figure is counted on the extract's first copies of each row, as they
arrived, unless said otherwise.
"""

import json
import os

import numpy as np
import pandas as pd

from config import config
from data_pipeline.application_cleaning import read_application_answers
from data_pipeline.common_cleaning import (
    convert_markup_to_plain_text,
    convert_phases,
    remove_duplicate_records,
)
from data_pipeline.connection_log_cleaning import read_log_answers


def _missing_cells(frame):
    counts = frame.isna().sum()
    return {str(column): int(count) for column, count in counts.items() if count > 0}


def _first_copies(raw_frame):
    return remove_duplicate_records(raw_frame)


def profile_dataset(raw_frame, clean_frame, target_column):
    """Account for one dataset: what arrived, what survived and what was missing."""
    duplicated = raw_frame.duplicated(keep="first")
    first_copies = raw_frame[~duplicated]
    return {
        "rows_received": int(len(raw_frame)),
        "rows_kept": int(len(clean_frame)),
        "rows_removed": int(len(raw_frame) - len(clean_frame)),
        "duplicate_rows": int(duplicated.sum()),
        "rows_missing_target": int(first_copies[target_column].isna().sum()),
        "columns": int(clean_frame.shape[1]),
        "missing_cells_as_received": _missing_cells(first_copies),
        "missing_cells_after_cleaning": _missing_cells(clean_frame),
    }


def _not_matching(values, pattern):
    given = values[values.notna()].astype(str)
    return int((~given.str.match(pattern)).sum())


def _references_not_canonical(first_copies):
    return _not_matching(
        first_copies[config.APPLICATION_REFERENCE_COLUMN],
        config.CANONICAL_APPLICATION_REFERENCE_PATTERN,
    )


def _numbers_not_plain(first_copies, number_patterns):
    return {
        column_name: _not_matching(first_copies[column_name], config.PLAIN_NUMBER_PATTERN)
        for column_name in number_patterns
        if column_name in first_copies.columns
    }


def _phases_not_numbers(first_copies):
    return {
        column_name: _not_matching(first_copies[column_name], config.CANONICAL_PHASES_PATTERN)
        for column_name in config.PHASE_COLUMNS
    }


def _impossible_phase_pairs(first_copies):
    phases = convert_phases(first_copies)
    supply = phases[config.SUPPLY_PHASES_COLUMN].astype("float64")
    equipment = phases[config.EQUIPMENT_PHASES_COLUMN].astype("float64")
    return int(((equipment > supply) & supply.notna() & equipment.notna()).sum())


def _by_notation(values, notations):
    given = values[values.notna()].astype(str)
    counts = {}
    for notation_name, pattern in notations.items():
        counts[notation_name] = int(given.str.match(pattern).sum())
    return counts


def _currents_by_notation(first_copies, current_phases):
    return {
        column_name: _by_notation(first_copies[column_name], config.CURRENT_NOTATIONS)
        for column_name in current_phases
        if column_name in first_copies.columns
    }


def _currents_unconvertible(first_copies, read, current_phases):
    return {
        column_name: int((first_copies[column_name].notna() & read[column_name].isna()).sum())
        for column_name in current_phases
        if column_name in first_copies.columns
    }


def _amounts_by_notation(first_copies, amount_readings):
    return {
        column_name: _by_notation(first_copies[column_name], reading["notations"])
        for column_name, reading in amount_readings.items()
        if column_name in first_copies.columns
    }


def _beyond(read, limits, compare):
    counts = {}
    for column_name, limit in limits.items():
        if column_name not in read.columns:
            continue
        numbers = read[column_name].astype("float64")
        counts[column_name] = int((numbers.notna() & compare(numbers, float(limit))).sum())
    return counts


def _outside_sizes(read, allowed_sizes):
    counts = {}
    for column_name, sizes in allowed_sizes.items():
        if column_name not in read.columns:
            continue
        numbers = read[column_name].astype("float64")
        outside = numbers.notna() & ~numbers.isin([float(size) for size in sizes])
        counts[column_name] = int(outside.sum())
    return counts


def _categories_not_canonical(first_copies, value_mappings):
    counts = {}
    for column_name, value_mapping in value_mappings.items():
        if column_name not in first_copies.columns:
            continue
        given = first_copies[column_name][first_copies[column_name].notna()].astype(str)
        counts[column_name] = int((~given.isin(set(value_mapping.values()))).sum())
    return counts


def _target_shares(clean_frame, target_column):
    shares = clean_frame[target_column].value_counts(normalize=True)
    return {
        str(value): round(float(share), config.TARGET_SHARE_DECIMALS)
        for value, share in shares.sort_index().items()
    }


def profile_history_details(raw_frame, clean_frame):
    """Account for the defects peculiar to the application history extracts."""
    first_copies = _first_copies(raw_frame)
    read = read_application_answers(
        first_copies, config.HISTORY_VALUE_MAPPINGS, config.FORM_WHOLE_NUMBER_PATTERNS
    )
    revisions = read[config.REVISION_NUMBER_COLUMN].astype("float64")
    latest = revisions.groupby(read[config.APPLICATION_REFERENCE_COLUMN]).transform("max")
    earlier = (revisions < latest).to_numpy(dtype=bool)
    answered = read[config.HISTORY_TARGET_COLUMN].notna().to_numpy(dtype=bool)
    return {
        "answered_earlier_revisions_removed": int((earlier & answered).sum()),
        "application_references_not_written_canonically": _references_not_canonical(
            first_copies
        ),
        "numbers_not_written_as_plain_numbers": _numbers_not_plain(
            first_copies, config.FORM_WHOLE_NUMBER_PATTERNS
        ),
        "phases_not_written_as_numbers": _phases_not_numbers(first_copies),
        "impossible_phase_pairs_as_received": _impossible_phase_pairs(first_copies),
        "currents_by_notation_as_written": _currents_by_notation(
            first_copies, config.FORM_CURRENT_PHASES
        ),
        "currents_unconvertible_without_phases": _currents_unconvertible(
            first_copies, read, config.FORM_CURRENT_PHASES
        ),
        "amounts_by_notation_as_written": _amounts_by_notation(
            first_copies, config.FORM_AMOUNT_READINGS
        ),
        "values_below_minimum_as_received": _beyond(
            read, config.FORM_MINIMUM_VALUES, lambda numbers, limit: numbers < limit
        ),
        "values_above_maximum_as_received": _beyond(
            read, config.FORM_MAXIMUM_VALUES, lambda numbers, limit: numbers > limit
        ),
        "values_outside_sizes_as_received": _outside_sizes(read, config.FORM_ALLOWED_SIZES),
        "category_values_not_written_canonically": _categories_not_canonical(
            first_copies, config.HISTORY_VALUE_MAPPINGS
        ),
        "target_shares": _target_shares(clean_frame, config.HISTORY_TARGET_COLUMN),
    }


def profile_log_details(raw_frame, clean_frame):
    """Account for the defects peculiar to the connection log extracts."""
    first_copies = _first_copies(raw_frame)
    read = read_log_answers(first_copies)
    target = read[config.LOG_TARGET_COLUMN].astype("float64")
    target_minimum = float(config.LOG_MINIMUM_VALUES[config.LOG_TARGET_COLUMN])
    return {
        "rows_with_impossible_target": int((target.notna() & (target < target_minimum)).sum()),
        "values_below_minimum_as_received": _beyond(
            read, config.LOG_MINIMUM_VALUES, lambda numbers, limit: numbers < limit
        ),
        "application_references_not_written_canonically": _references_not_canonical(
            first_copies
        ),
        "numbers_not_written_as_plain_numbers": _numbers_not_plain(
            first_copies, config.LOG_WHOLE_NUMBER_PATTERNS
        ),
        "phases_not_written_as_numbers": _phases_not_numbers(first_copies),
        "impossible_phase_pairs_as_received": _impossible_phase_pairs(first_copies),
        "currents_by_notation_as_written": _currents_by_notation(
            first_copies, config.LOG_CURRENT_PHASES
        ),
        "currents_unconvertible_without_phases": _currents_unconvertible(
            first_copies, read, config.LOG_CURRENT_PHASES
        ),
        "amounts_by_notation_as_written": _amounts_by_notation(
            first_copies, config.LOG_AMOUNT_READINGS
        ),
        "values_outside_sizes_as_received": _outside_sizes(read, config.LOG_ALLOWED_SIZES),
        "category_values_not_written_canonically": _categories_not_canonical(
            first_copies, config.LOG_VALUE_MAPPINGS
        ),
        "median_actual_working_days": float(clean_frame[config.LOG_TARGET_COLUMN].median()),
    }


def profile_sentence_details(raw_frame, clean_frame):
    """Account for the defects peculiar to free text."""
    first_copies = _first_copies(raw_frame)
    texts = first_copies[config.SENTENCE_TEXT_COLUMN]
    given = texts[texts.notna()].astype(str)
    plain = convert_markup_to_plain_text(texts)
    plain_given = plain[plain.notna()].astype(str)
    raw_lengths = pd.to_numeric(first_copies[config.SENTENCE_LENGTH_COLUMN], errors="coerce")
    plain_lengths = plain.map(lambda text: np.nan if pd.isna(text) else len(str(text)))
    disagreeing = int((raw_lengths != plain_lengths).sum())
    word_counts = plain.map(lambda text: 0 if pd.isna(text) else len(str(text).split()))
    labelled = first_copies[config.SENTENCE_TARGET_COLUMN].notna()
    cleaned_words = clean_frame[config.SENTENCE_TEXT_COLUMN].map(
        lambda text: len(str(text).split())
    )
    return {
        "sentences_with_markup": int(given.str.contains(config.MARKUP_PATTERN, regex=True).sum()),
        "sentences_with_encoding_artifacts": int(
            given.str.contains(config.ENCODING_ARTIFACT_PATTERN, regex=True).sum()
        ),
        "sentences_in_capitals": int(plain_given.map(str.isupper).sum()),
        "sentence_lengths_disagreeing_with_plain_text_as_received": disagreeing,
        "rows_with_too_few_words": int(
            (labelled & (word_counts < config.MINIMUM_SENTENCE_WORDS)).sum()
        ),
        "shortest_sentence_words": int(cleaned_words.min()) if len(cleaned_words) else 0,
        "application_references_not_written_canonically": _references_not_canonical(
            first_copies
        ),
        "category_values_not_written_canonically": _categories_not_canonical(
            first_copies, config.SENTENCE_VALUE_MAPPINGS
        ),
        "target_shares": _target_shares(clean_frame, config.SENTENCE_TARGET_COLUMN),
    }


def _plain_json(value):
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"{type(value).__name__} cannot be written to the quality report")


def write_quality_report(profiles):
    """Write every dataset's profile to the quality report as sorted, indented JSON."""
    folder = os.path.dirname(config.DATA_QUALITY_REPORT_FILE)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(config.DATA_QUALITY_REPORT_FILE, "w", encoding="utf-8") as report_file:
        json.dump(profiles, report_file, indent=config.JSON_INDENT, sort_keys=True,
                  default=_plain_json)

