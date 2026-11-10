"""Cleaning shared by the past statement sentences and the live statements."""

from config import config
from data_pipeline.common_cleaning import (
    clean_statement_text,
    convert_application_references,
    convert_whole_numbers,
    normalize_category_values,
    refuse_missing_values,
    refuse_repeated_references,
    remove_duplicate_records,
)


def clean_document_records(frame, value_mappings, whole_number_patterns, id_column,
                           text_column):
    """Clean the rows of statements, whether past sentences or live statements."""
    rows = remove_duplicate_records(frame)
    rows = refuse_missing_values(rows, [id_column, config.APPLICATION_REFERENCE_COLUMN])
    rows = refuse_repeated_references(rows, id_column)
    rows = normalize_category_values(rows, value_mappings)
    rows[config.APPLICATION_REFERENCE_COLUMN] = convert_application_references(
        rows[config.APPLICATION_REFERENCE_COLUMN]
    )
    rows = convert_whole_numbers(rows, whole_number_patterns)
    rows[text_column] = clean_statement_text(rows[text_column])
    return rows
