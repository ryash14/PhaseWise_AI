"""Requirement counts, network trigger flags, model inputs and the model pipeline."""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from config import config
from tools.screening_tools import find_network_triggers, screen_application


def add_requirement_counts(dataframe, standards):
    """Add the Met, Not met and Not documented counts each row's own standard gives it."""
    counted = dataframe.copy()
    columns = {column_name: [] for column_name in config.REQUIREMENT_COUNT_RESULTS}
    for application in dataframe.to_dict("records"):
        technology = application[config.TECHNOLOGY_COLUMN]
        standard = standards.get(technology)
        if standard is None:
            raise ValueError(
                str(application[config.APPLICATION_REFERENCE_COLUMN]) + ": "
                + config.NO_STANDARD_CONFIGURED_MESSAGE.format(technology=technology)
            )
        screening = screen_application(application, standard)
        for column_name in config.REQUIREMENT_COUNT_RESULTS:
            columns[column_name].append(int(screening[column_name]))
    for column_name, values in columns.items():
        counted[column_name] = pd.Series(values, index=counted.index, dtype="int64")
    return counted


def add_network_trigger_flags(dataframe):
    """Add a 1/0 flag for every network trigger each row meets."""
    flagged = dataframe.copy()
    flags = {column_name: [] for column_name in config.NETWORK_TRIGGER_FLAG_COLUMNS.values()}
    for row in dataframe.to_dict("records"):
        triggers = find_network_triggers(row)
        for trigger_name, column_name in config.NETWORK_TRIGGER_FLAG_COLUMNS.items():
            flags[column_name].append(int(trigger_name in triggers))
    for column_name, values in flags.items():
        flagged[column_name] = pd.Series(values, index=flagged.index, dtype="int64")
    return flagged


def build_feature_frame(dataframe, numeric_columns, categorical_columns):
    """Lay a table out exactly as a model is fitted and scored on it."""
    features = pd.DataFrame(index=dataframe.index)
    for column_name in numeric_columns:
        features[column_name] = pd.to_numeric(
            dataframe[column_name].astype(object).where(dataframe[column_name].notna(), np.nan),
            errors="raise",
        ).astype("float64")
    for column_name in categorical_columns:
        column = dataframe[column_name]
        features[column_name] = column.astype(object).where(column.notna(), np.nan)
    return features


def build_model_pipeline(estimator, numeric_columns, categorical_columns):
    """Join the input preparation and the estimator into one pipeline."""
    numbers = Pipeline(
        [
            ("fill", SimpleImputer(strategy=config.NUMBER_FILL_STRATEGY)),
            ("scale", StandardScaler()),
        ]
    )
    words = Pipeline(
        [
            ("fill", SimpleImputer(strategy=config.CATEGORY_FILL_STRATEGY)),
            ("encode", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    preparation = ColumnTransformer(
        [
            ("numbers", numbers, list(numeric_columns)),
            ("words", words, list(categorical_columns)),
        ],
        remainder="drop",
    )
    return Pipeline(
        [
            (config.PREPROCESSING_STEP_NAME, preparation),
            (config.MODEL_STEP_NAME, estimator),
        ]
    )
