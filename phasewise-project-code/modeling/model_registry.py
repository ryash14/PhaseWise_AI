"""Saves and loads the models and their feature schemas, and saves their scores."""

import json
import os

import joblib

from config import config


def _make_folder(file_path):
    folder = os.path.dirname(file_path)
    if folder:
        os.makedirs(folder, exist_ok=True)


def save_model(model, file_path):
    """Put the whole fitted pipeline on disk, compressed, replacing any earlier file."""
    _make_folder(file_path)
    joblib.dump(model, file_path, compress=config.MODEL_FILE_COMPRESSION)


def save_feature_schema(feature_names, file_path):
    """Record the columns a saved model expects, in order."""
    _make_folder(file_path)
    with open(file_path, "w", encoding="utf-8") as schema_file:
        json.dump([str(name) for name in feature_names], schema_file, indent=config.JSON_INDENT)


def load_model(file_path):
    """Bring a saved model back, ready to score."""
    return joblib.load(file_path)


def load_feature_schema(file_path):
    """Read back the columns a model expects, in the order saved."""
    with open(file_path, encoding="utf-8") as schema_file:
        return list(json.load(schema_file))


def save_metrics(metrics):
    """Leave every model's scores on disk as sorted, indented JSON."""
    _make_folder(config.MODEL_METRICS_FILE)
    with open(config.MODEL_METRICS_FILE, "w", encoding="utf-8") as metrics_file:
        json.dump(metrics, metrics_file, indent=config.JSON_INDENT, sort_keys=True)
