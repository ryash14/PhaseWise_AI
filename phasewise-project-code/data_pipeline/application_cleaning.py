"""The repairs an application's form needs, shared by the history and the live queue."""

from config import config
from data_pipeline.common_cleaning import (
    convert_amounts,
    convert_application_references,
    convert_currents,
    convert_phases,
    convert_whole_numbers,
    keep_latest_revision_of_each_application,
    normalize_category_values,
    refuse_unreadable_identifiers,
    remove_duplicate_records,
    treat_impossible_phase_pairs_as_missing,
    treat_values_above_maximum_as_missing,
    treat_values_below_minimum_as_missing,
    treat_values_outside_sizes_as_missing,
)


def read_application_answers(frame, value_mappings, whole_number_patterns):
    """Read every answer on a form as the Connection Rules read it; no row is removed."""
    forms = normalize_category_values(frame, value_mappings)
    forms[config.APPLICATION_REFERENCE_COLUMN] = convert_application_references(
        forms[config.APPLICATION_REFERENCE_COLUMN]
    )
    forms = refuse_unreadable_identifiers(forms, config.FORM_IDENTIFIER_PATTERNS)
    forms = convert_whole_numbers(forms, whole_number_patterns)
    forms = convert_phases(forms)
    forms = treat_impossible_phase_pairs_as_missing(forms)
    forms = convert_currents(forms, config.FORM_CURRENT_PHASES)
    forms = convert_amounts(forms, config.FORM_AMOUNT_READINGS)
    return forms


def clean_application_records(frame, value_mappings, whole_number_patterns):
    """Turn raw application forms into one clean row per application."""
    forms = remove_duplicate_records(frame)
    forms = read_application_answers(forms, value_mappings, whole_number_patterns)
    forms = treat_values_below_minimum_as_missing(forms, config.FORM_MINIMUM_VALUES)
    forms = treat_values_above_maximum_as_missing(forms, config.FORM_MAXIMUM_VALUES)
    forms = treat_values_outside_sizes_as_missing(forms, config.FORM_ALLOWED_SIZES)
    return keep_latest_revision_of_each_application(forms)
