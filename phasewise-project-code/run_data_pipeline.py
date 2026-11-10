"""Entry point 2: cleans the five raw extracts and writes the data quality report.

Run from the Project folder:  python run_data_pipeline.py
"""

import os

from config import config
from data_pipeline.connection_log_cleaning import clean_connection_log_dataset
from data_pipeline.dataset_loader import load_raw_dataset, save_processed_dataset
from data_pipeline.history_cleaning import clean_history_dataset
from data_pipeline.quality_profiler import (
    profile_dataset,
    profile_history_details,
    profile_log_details,
    profile_sentence_details,
    write_quality_report,
)
from data_pipeline.sentence_cleaning import clean_sentence_dataset

DATASET_JOBS = [
    (config.RAW_APPLICATION_HISTORY_TRAIN_FILE, config.CLEAN_APPLICATION_HISTORY_TRAIN_FILE,
     clean_history_dataset, config.HISTORY_TARGET_COLUMN, profile_history_details),
    (config.RAW_APPLICATION_HISTORY_EVAL_FILE, config.CLEAN_APPLICATION_HISTORY_EVAL_FILE,
     clean_history_dataset, config.HISTORY_TARGET_COLUMN, profile_history_details),
    (config.RAW_CONNECTION_LOGS_TRAIN_FILE, config.CLEAN_CONNECTION_LOGS_TRAIN_FILE,
     clean_connection_log_dataset, config.LOG_TARGET_COLUMN, profile_log_details),
    (config.RAW_CONNECTION_LOGS_EVAL_FILE, config.CLEAN_CONNECTION_LOGS_EVAL_FILE,
     clean_connection_log_dataset, config.LOG_TARGET_COLUMN, profile_log_details),
    (config.RAW_STATEMENT_SENTENCES_FILE, config.CLEAN_STATEMENT_SENTENCES_FILE,
     clean_sentence_dataset, config.SENTENCE_TARGET_COLUMN, profile_sentence_details),
]


def main():
    """Clean all five extracts first, then save them all and write the report."""
    cleaned = []
    profiles = {}
    for raw_path, clean_path, cleaner, target_column, detail_profiler in DATASET_JOBS:
        raw_frame = load_raw_dataset(raw_path)
        clean_frame = cleaner(raw_frame)
        dataset_name = os.path.splitext(os.path.basename(raw_path))[0]
        profile = profile_dataset(raw_frame, clean_frame, target_column)
        profile.update(detail_profiler(raw_frame, clean_frame))
        profiles[dataset_name] = profile
        cleaned.append((dataset_name, clean_path, clean_frame, profile))
    for dataset_name, clean_path, clean_frame, profile in cleaned:
        save_processed_dataset(clean_frame, clean_path)
        print(
            f"{dataset_name:<{config.DATASET_NAME_WIDTH}}"
            f"{profile['rows_received']:>{config.ROW_COUNT_WIDTH}} received -> "
            f"{profile['rows_kept']:>{config.ROW_COUNT_WIDTH}} kept  "
            f"({profile['rows_removed']} removed)"
        )
    write_quality_report(profiles)
    print(f"quality report written to {config.DATA_QUALITY_REPORT_FILE}")


if __name__ == "__main__":
    main()
