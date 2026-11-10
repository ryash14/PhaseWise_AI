"""Reads raw extracts as text and reads/writes cleaned tables.

This is the only data preparation module that touches CSV files.
"""

import os

import numpy as np
import pandas as pd

from config import config


def load_raw_dataset(file_path):
    """Read one raw file as text, guessing nothing.

    Every value is text without surrounding whitespace; only a value matching
    one of config.NULL_TOKENS (ignoring case and spaces) becomes NaN.
    """
    frame = pd.read_csv(file_path, dtype=str, keep_default_na=False, na_filter=False)
    null_tokens = {token.strip().lower() for token in config.NULL_TOKENS}
    for column_name in frame.columns:
        stripped = frame[column_name].astype(str).str.strip()
        is_missing = stripped.str.lower().isin(null_tokens)
        frame[column_name] = stripped.where(~is_missing, np.nan).astype(object)
    return frame


def save_processed_dataset(dataframe, file_path):
    """Write a cleaned table to disk without an index column."""
    folder = os.path.dirname(file_path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    dataframe.to_csv(file_path, index=False)


def load_processed_dataset(file_path):
    """Read a cleaned table, types taken from its contents; only empty cells are missing."""
    return pd.read_csv(file_path, keep_default_na=False, na_values=[""], low_memory=False)
