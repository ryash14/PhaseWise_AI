"""The network work likelihood and the expected working days of one application."""

from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from config import config
from data_pipeline.feature_builder import build_feature_frame


def _refuse_other_screening(application, screening):
    application_reference = application.get(config.APPLICATION_REFERENCE_COLUMN)
    if screening.get("application_reference") != application_reference:
        raise ValueError(
            config.SCREENING_OF_ANOTHER_APPLICATION_MESSAGE.format(
                screening_reference=screening.get("application_reference"),
                application_reference=application_reference,
            )
        )


def _model_inputs(application, screening, numeric_columns, categorical_columns,
                  feature_names, with_counts):
    row = dict(application)
    if with_counts:
        for column_name in config.REQUIREMENT_COUNT_RESULTS:
            row[column_name] = screening[column_name]
    for trigger_name, column_name in config.NETWORK_TRIGGER_FLAG_COLUMNS.items():
        row[column_name] = int(trigger_name in screening["network_triggers"])
    for column_name in list(numeric_columns) + list(categorical_columns):
        row.setdefault(column_name, None)
    features = build_feature_frame(pd.DataFrame([row]), numeric_columns, categorical_columns)
    if list(features.columns) != list(feature_names):
        raise ValueError(
            f"The inputs {list(features.columns)} are not the saved schema "
            f"{list(feature_names)} the model was fitted on"
        )
    return features


def estimate_network_work_likelihood(network_work_model, feature_names, application,
                                     screening):
    """The probability of network work, rounded half up to the step, and its band."""
    _refuse_other_screening(application, screening)
    features = _model_inputs(
        application,
        screening,
        config.NETWORK_WORK_NUMERIC_FEATURES,
        config.NETWORK_WORK_CATEGORICAL_FEATURES,
        feature_names,
        with_counts=True,
    )
    positive = list(network_work_model.classes_).index(1)
    probability = float(network_work_model.predict_proba(features)[0, positive])
    figure = Decimal(repr(probability)).quantize(config.LIKELIHOOD_STEP, rounding=ROUND_HALF_UP)
    if figure >= config.HIGH_LIKELIHOOD_MINIMUM:
        band = config.HIGH_LIKELIHOOD_BAND
    elif figure >= config.MEDIUM_LIKELIHOOD_MINIMUM:
        band = config.MEDIUM_LIKELIHOOD_BAND
    else:
        band = config.LOW_LIKELIHOOD_BAND
    return {"network_work_likelihood": float(figure), "likelihood_band": band}


def estimate_expected_working_days(duration_model, feature_names, application, screening):
    """The working days the connection is expected to take, and whether a delay is expected."""
    _refuse_other_screening(application, screening)
    features = _model_inputs(
        application,
        screening,
        config.DURATION_NUMERIC_FEATURES,
        config.DURATION_CATEGORICAL_FEATURES,
        feature_names,
        with_counts=False,
    )
    forecast = float(duration_model.predict(features)[0])
    expected = int(
        Decimal(repr(forecast)).quantize(config.WORKING_DAY_STEP, rounding=ROUND_HALF_UP)
    )
    planned_value = application.get(config.PLANNED_WORKING_DAYS_COLUMN)
    if planned_value is None or pd.isna(planned_value):
        planned = None
        delay = None
    else:
        planned = int(planned_value)
        delay = bool(expected - planned > config.DELAY_MARGIN_WORKING_DAYS)
    return {
        "expected_working_days": expected,
        "planned_working_days": planned,
        "delay_expected": delay,
    }


def describe_expected_working_days(duration):
    """The expected working days in the configuration's words."""
    if duration["delay_expected"] is None:
        return config.EXPECTED_DAYS_WITHOUT_PLAN_TEMPLATE.format(
            expected_working_days=duration["expected_working_days"]
        )
    template = config.DELAY_TEMPLATE if duration["delay_expected"] else config.NO_DELAY_TEMPLATE
    return template.format(
        expected_working_days=duration["expected_working_days"],
        planned_working_days=duration["planned_working_days"],
    )
