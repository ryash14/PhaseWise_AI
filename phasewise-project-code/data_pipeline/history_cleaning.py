"""Produces the table the network work model learns from."""

from config import config
from data_pipeline.application_cleaning import clean_application_records
from data_pipeline.common_cleaning import remove_rows_missing_target


def clean_history_dataset(frame):
    """One row per application, at its highest revision, that records an outcome."""
    applications = clean_application_records(
        frame, config.HISTORY_VALUE_MAPPINGS, config.FORM_WHOLE_NUMBER_PATTERNS
    )
    return remove_rows_missing_target(applications, config.HISTORY_TARGET_COLUMN)
