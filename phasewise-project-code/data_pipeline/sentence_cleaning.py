"""Produces the table the sentence model learns from."""

import pandas as pd

from config import config
from data_pipeline.document_cleaning import clean_document_records


def _word_count(text):
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return 0
    return len(str(text).split())


def clean_sentence_dataset(frame):
    """Clean labelled statement sentences, re-measure them and drop the unusable ones."""
    sentences = clean_document_records(
        frame,
        config.SENTENCE_VALUE_MAPPINGS,
        config.SENTENCE_WHOLE_NUMBER_PATTERNS,
        config.SENTENCE_ID_COLUMN,
        config.SENTENCE_TEXT_COLUMN,
    )
    texts = sentences[config.SENTENCE_TEXT_COLUMN]
    lengths = [pd.NA if pd.isna(text) else len(str(text)) for text in texts]
    sentences[config.SENTENCE_LENGTH_COLUMN] = pd.array(lengths, dtype=config.WHOLE_NUMBER_DTYPE)
    labelled = sentences[config.SENTENCE_TARGET_COLUMN].notna()
    long_enough = texts.map(_word_count) >= config.MINIMUM_SENTENCE_WORDS
    return sentences[labelled & long_enough].reset_index(drop=True)
