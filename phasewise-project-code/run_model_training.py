"""Entry point 3: trains, scores and saves the three models.

Run from the Project folder:  python run_model_training.py
Nothing is saved unless every model reaches the minimum the configuration sets.
"""

import sklearn
from sklearn.model_selection import train_test_split

from config import config
from data_pipeline.dataset_loader import load_processed_dataset
from data_pipeline.feature_builder import (
    add_network_trigger_flags,
    add_requirement_counts,
    build_feature_frame,
)
from knowledge.pdf_extraction import extract_text_from_directory
from knowledge.standard_reading import read_connection_standard
from modeling.duration_model import train_duration_model
from modeling.model_registry import save_feature_schema, save_metrics, save_model
from modeling.network_work_model import train_network_work_model
from modeling.sentence_model import train_sentence_model


def _encoded_outcomes(frame):
    target = frame[config.HISTORY_TARGET_COLUMN]
    unknown = sorted(set(target.dropna().astype(str)) - set(config.NETWORK_WORK_TARGET_ENCODING))
    if unknown or target.isna().any():
        raise ValueError(
            f"{config.HISTORY_TARGET_COLUMN} holds outcomes the encoding does not know: "
            + ", ".join(unknown or ["a blank outcome"])
        )
    return target.map(config.NETWORK_WORK_TARGET_ENCODING).astype(int)


def _network_work_inputs(frame, standards):
    prepared = add_network_trigger_flags(add_requirement_counts(frame, standards))
    features = build_feature_frame(
        prepared, config.NETWORK_WORK_NUMERIC_FEATURES, config.NETWORK_WORK_CATEGORICAL_FEATURES
    )
    return features, _encoded_outcomes(prepared)


def _duration_inputs(frame):
    prepared = add_network_trigger_flags(frame)
    features = build_feature_frame(
        prepared, config.DURATION_NUMERIC_FEATURES, config.DURATION_CATEGORICAL_FEATURES
    )
    return features, prepared[config.LOG_TARGET_COLUMN].astype(float)


def _algorithm(model, every_step=False):
    if every_step:
        return " + ".join(type(step).__name__ for _, step in model.steps)
    return type(model.named_steps[config.MODEL_STEP_NAME]).__name__


def _print_scores(label, held_label, held, train, gap, extra=""):
    print(f"  {label:<15} held-out {held_label} {held:.4f}{extra}  (train {train:.4f}, gap {gap:+.4f})")


def main():
    """Train the three models, check each against its minimum, then save them all."""
    print("training three models")
    documents = extract_text_from_directory(config.DOCS_DIRECTORY)
    standards = {
        technology: read_connection_standard(technology, documents)
        for technology in config.CONNECTION_STANDARD_DOCUMENTS
    }

    history_train = load_processed_dataset(config.CLEAN_APPLICATION_HISTORY_TRAIN_FILE)
    history_eval = load_processed_dataset(config.CLEAN_APPLICATION_HISTORY_EVAL_FILE)
    work_train_x, work_train_y = _network_work_inputs(history_train, standards)
    work_eval_x, work_eval_y = _network_work_inputs(history_eval, standards)
    work_model, work_scores = train_network_work_model(
        work_train_x, work_train_y, work_eval_x, work_eval_y
    )

    logs_train = load_processed_dataset(config.CLEAN_CONNECTION_LOGS_TRAIN_FILE)
    logs_eval = load_processed_dataset(config.CLEAN_CONNECTION_LOGS_EVAL_FILE)
    days_train_x, days_train_y = _duration_inputs(logs_train)
    days_eval_x, days_eval_y = _duration_inputs(logs_eval)
    days_model, days_scores = train_duration_model(
        days_train_x, days_train_y, days_eval_x, days_eval_y
    )

    sentences = load_processed_dataset(config.CLEAN_STATEMENT_SENTENCES_FILE)
    text_train, text_held, type_train, type_held = train_test_split(
        sentences[config.SENTENCE_TEXT_COLUMN],
        sentences[config.SENTENCE_TARGET_COLUMN],
        test_size=config.SENTENCE_HELD_OUT_SHARE,
        stratify=sentences[config.SENTENCE_TARGET_COLUMN],
        random_state=config.RANDOM_SEED,
    )
    sentence_model, sentence_scores = train_sentence_model(
        text_train, type_train, text_held, type_held
    )

    _print_scores("network work", "ROC AUC", work_scores["held_out_roc_auc"],
                  work_scores["train_roc_auc"], work_scores["generalisation_gap"])
    _print_scores("duration", "R2", days_scores["held_out_r2"], days_scores["train_r2"],
                  days_scores["generalisation_gap"],
                  f"  MAE {days_scores['mean_absolute_error']:.4f} working days")
    _print_scores("sentence", "macro F1", sentence_scores["held_out_macro_f1"],
                  sentence_scores["train_macro_f1"], sentence_scores["generalisation_gap"])

    shortfalls = []
    for label, score, minimum in [
        ("network work held-out ROC AUC", work_scores["held_out_roc_auc"],
         config.MINIMUM_NETWORK_WORK_ROC_AUC),
        ("duration held-out R2", days_scores["held_out_r2"], config.MINIMUM_DURATION_R2),
        ("sentence held-out macro F1", sentence_scores["held_out_macro_f1"],
         config.MINIMUM_SENTENCE_MACRO_F1),
    ]:
        if score < minimum:
            shortfalls.append(f"{label} {score:.4f} is below {minimum}")
    if shortfalls:
        raise SystemExit("Nothing was saved: " + "; ".join(shortfalls))

    save_model(work_model, config.NETWORK_WORK_MODEL_FILE)
    save_model(days_model, config.DURATION_MODEL_FILE)
    save_model(sentence_model, config.SENTENCE_MODEL_FILE)
    save_feature_schema(list(work_model.feature_names_in_), config.NETWORK_WORK_SCHEMA_FILE)
    save_feature_schema(list(days_model.feature_names_in_), config.DURATION_SCHEMA_FILE)
    save_metrics(
        {
            "network_work": {
                "algorithm": _algorithm(work_model),
                "training_rows": int(len(work_train_x)),
                "held_out_rows": int(len(work_eval_x)),
                "scores": work_scores,
                "minimum_required": config.MINIMUM_NETWORK_WORK_ROC_AUC,
                "scikit_learn_version": sklearn.__version__,
            },
            "duration": {
                "algorithm": _algorithm(days_model),
                "training_rows": int(len(days_train_x)),
                "held_out_rows": int(len(days_eval_x)),
                "scores": days_scores,
                "minimum_required": config.MINIMUM_DURATION_R2,
                "scikit_learn_version": sklearn.__version__,
            },
            "sentence": {
                "algorithm": _algorithm(sentence_model, every_step=True),
                "training_rows": int(len(text_train)),
                "held_out_rows": int(len(text_held)),
                "scores": sentence_scores,
                "minimum_required": config.MINIMUM_SENTENCE_MACRO_F1,
                "scikit_learn_version": sklearn.__version__,
            },
        }
    )
    print(f"metrics written to {config.MODEL_METRICS_FILE}")
    print("every model reaches the minimum the configuration sets for it")


if __name__ == "__main__":
    main()
