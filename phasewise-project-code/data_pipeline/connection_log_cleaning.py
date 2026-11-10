"""Produces the table the duration model learns from."""

from config import config
from data_pipeline.common_cleaning import (
    convert_amounts,
    convert_application_references,
    convert_currents,
    convert_phases,
    convert_whole_numbers,
    normalize_category_values,
    refuse_missing_values,
    refuse_repeated_references,
    refuse_unreadable_identifiers,
    remove_duplicate_records,
    remove_rows_missing_target,
    treat_impossible_phase_pairs_as_missing,
    treat_values_below_minimum_as_missing,
    treat_values_outside_sizes_as_missing,
)


def read_log_answers(frame):
    """Read every answer of a log as the Connection Rules read it; no row is removed."""
    logs = normalize_category_values(frame, config.LOG_VALUE_MAPPINGS)
    logs[config.APPLICATION_REFERENCE_COLUMN] = convert_application_references(
        logs[config.APPLICATION_REFERENCE_COLUMN]
    )
    logs = refuse_unreadable_identifiers(logs, config.LOG_IDENTIFIER_PATTERNS)
    logs = convert_whole_numbers(logs, config.LOG_WHOLE_NUMBER_PATTERNS)
    logs = convert_phases(logs)
    logs = treat_impossible_phase_pairs_as_missing(logs)
    logs = convert_currents(logs, config.LOG_CURRENT_PHASES)
    logs = convert_amounts(logs, config.LOG_AMOUNT_READINGS)
    return logs


def clean_connection_log_dataset(frame):
    """One row per application with the working days its connection really took."""
    logs = remove_duplicate_records(frame)
    logs = refuse_missing_values(logs, [config.APPLICATION_REFERENCE_COLUMN])
    logs = read_log_answers(logs)
    logs = refuse_repeated_references(logs, config.APPLICATION_REFERENCE_COLUMN)
    logs = treat_values_below_minimum_as_missing(logs, config.LOG_MINIMUM_VALUES)
    logs = treat_values_outside_sizes_as_missing(logs, config.LOG_ALLOWED_SIZES)
    return remove_rows_missing_target(logs, config.LOG_TARGET_COLUMN)
