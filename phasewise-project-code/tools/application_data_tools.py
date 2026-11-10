"""Reads the live queue, its statements and the connection history, one application at a time."""

import numpy as np
import pandas as pd

from config import config
from data_pipeline.application_cleaning import clean_application_records
from data_pipeline.dataset_loader import load_processed_dataset, load_raw_dataset
from data_pipeline.document_cleaning import clean_document_records


def _plain(value):
    """A table cell as a plain Python value, a blank as None."""
    if value is None or value is pd.NA:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if np.isnan(value) else float(value)
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def load_open_applications():
    """The live queue, read through the same cleaning as the history."""
    return clean_application_records(
        load_raw_dataset(config.OPEN_APPLICATIONS_FILE),
        config.FORM_VALUE_MAPPINGS,
        config.LIVE_WHOLE_NUMBER_PATTERNS,
    )


def load_application_documents():
    """The statements attached to the open applications."""
    return clean_document_records(
        load_raw_dataset(config.APPLICATION_DOCUMENTS_FILE),
        config.DOCUMENT_VALUE_MAPPINGS,
        config.DOCUMENT_WHOLE_NUMBER_PATTERNS,
        config.DOCUMENT_ID_COLUMN,
        config.DOCUMENT_TEXT_COLUMN,
    )


def load_connection_history():
    """Every application already connected: the cleaned training then held-out history."""
    return pd.concat(
        [
            load_processed_dataset(config.CLEAN_APPLICATION_HISTORY_TRAIN_FILE),
            load_processed_dataset(config.CLEAN_APPLICATION_HISTORY_EVAL_FILE),
        ],
        ignore_index=True,
    )


def fetch_application(applications, application_reference):
    """One application's own answers, column by column, a blank as None."""
    rows = applications[applications[config.APPLICATION_REFERENCE_COLUMN] == application_reference]
    if len(rows) == 0:
        raise ValueError(
            config.UNKNOWN_APPLICATION_MESSAGE.format(application_reference=application_reference)
        )
    row = rows.iloc[0]
    return {str(column_name): _plain(row[column_name]) for column_name in applications.columns}


def fetch_application_documents(documents, application):
    """The statements attached to one application, in document identifier order."""
    reference = application[config.APPLICATION_REFERENCE_COLUMN]
    attached = documents[documents[config.APPLICATION_REFERENCE_COLUMN] == reference]
    attached = attached.sort_values(config.DOCUMENT_ID_COLUMN, kind="stable")
    return [
        {str(column_name): _plain(value) for column_name, value in record.items()}
        for record in attached.to_dict("records")
    ]


def rank_application_queue(applications):
    """Heat pumps replacing failed heating first, then the rest, each by reference."""
    first, rest = [], []
    for record in applications.to_dict("records"):
        reference = record[config.APPLICATION_REFERENCE_COLUMN]
        heat_pump = record.get(config.TECHNOLOGY_COLUMN) == config.HEAT_PUMP
        failed = record.get(config.URGENCY_COLUMN) == config.URGENCY_HEATING_FAILED
        (first if heat_pump and failed else rest).append(reference)
    return sorted(first) + sorted(rest)


def _describe_value(value):
    plain = _plain(value)
    if plain is None:
        return config.NOT_GIVEN_TEXT
    if isinstance(plain, bool):
        return str(plain)
    if isinstance(plain, int):
        return f"{plain:,}"
    if isinstance(plain, float) and plain.is_integer():
        return f"{int(plain):,}"
    return str(plain)


def describe_record(record):
    """A record in the words a page and a prompt show: every value as text."""
    return {key: _describe_value(value) for key, value in record.items()}
