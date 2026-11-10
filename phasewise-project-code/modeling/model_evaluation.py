"""Scores a fitted model on training and held-out data, never fitting it again."""

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    mean_absolute_error,
    r2_score,
    roc_auc_score,
)

from config import config


def _rounded(value):
    return round(float(value), config.METRIC_DECIMALS)


def _positive_scores(model, features):
    positive = list(model.classes_).index(1)
    return model.predict_proba(features)[:, positive]


def evaluate_classifier(model, train_features, train_target, held_out_features,
                        held_out_target):
    """How well the network work model ranks unseen applications, and whether it is calibrated."""
    train_scores = _positive_scores(model, train_features)
    held_out_scores = _positive_scores(model, held_out_features)
    train_auc = roc_auc_score(train_target, train_scores)
    held_out_auc = roc_auc_score(held_out_target, held_out_scores)
    return {
        "train_roc_auc": _rounded(train_auc),
        "held_out_roc_auc": _rounded(held_out_auc),
        "brier_score": _rounded(brier_score_loss(held_out_target, held_out_scores)),
        "mean_predicted_probability": _rounded(np.mean(held_out_scores)),
        "positive_share": _rounded(np.mean(np.asarray(held_out_target, dtype=float))),
        "generalisation_gap": _rounded(train_auc - held_out_auc),
    }


def evaluate_regressor(model, train_features, train_target, held_out_features,
                       held_out_target):
    """How close the duration model's working days are on unseen connections."""
    train_forecast = model.predict(train_features)
    held_out_forecast = model.predict(held_out_features)
    train_r2 = r2_score(train_target, train_forecast)
    held_out_r2 = r2_score(held_out_target, held_out_forecast)
    training_average = float(np.mean(np.asarray(train_target, dtype=float)))
    return {
        "train_r2": _rounded(train_r2),
        "held_out_r2": _rounded(held_out_r2),
        "mean_absolute_error": _rounded(mean_absolute_error(held_out_target, held_out_forecast)),
        "average_estimate_mean_absolute_error": _rounded(
            mean_absolute_error(held_out_target, [training_average] * len(held_out_target))
        ),
        "lowest_prediction": _rounded(np.min(held_out_forecast)),
        "highest_prediction": _rounded(np.max(held_out_forecast)),
        "generalisation_gap": _rounded(train_r2 - held_out_r2),
    }


def evaluate_text_classifier(model, train_text, train_target, held_out_text, held_out_target):
    """How well the sentence model names every type of sentence, not only the common ones."""
    train_predicted = model.predict(list(train_text))
    held_out_predicted = model.predict(list(held_out_text))
    train_f1 = f1_score(train_target, train_predicted, average="macro")
    held_out_f1 = f1_score(held_out_target, held_out_predicted, average="macro")
    classes = list(model.classes_)
    per_class = f1_score(
        held_out_target, held_out_predicted, labels=classes, average=None, zero_division=0
    )
    return {
        "train_macro_f1": _rounded(train_f1),
        "held_out_macro_f1": _rounded(held_out_f1),
        "accuracy": _rounded(accuracy_score(held_out_target, held_out_predicted)),
        "weighted_f1": _rounded(
            f1_score(held_out_target, held_out_predicted, average="weighted")
        ),
        "generalisation_gap": _rounded(train_f1 - held_out_f1),
        "per_class_f1": {
            str(label): _rounded(score) for label, score in zip(classes, per_class)
        },
    }
