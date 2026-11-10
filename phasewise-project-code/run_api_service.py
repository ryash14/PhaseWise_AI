"""Entry point 5: starts the REST service on port 8081, after checking its inputs exist.

Run from the Project folder:  python run_api_service.py   (leave it running)
"""

import os
import sys

from config import config

REQUIRED_BEFORE_STARTING = [
    (config.CLEAN_APPLICATION_HISTORY_TRAIN_FILE, "run_data_pipeline.py"),
    (config.CLEAN_APPLICATION_HISTORY_EVAL_FILE, "run_data_pipeline.py"),
    (config.NETWORK_WORK_MODEL_FILE, "run_model_training.py"),
    (config.DURATION_MODEL_FILE, "run_model_training.py"),
    (config.SENTENCE_MODEL_FILE, "run_model_training.py"),
    (config.NETWORK_WORK_SCHEMA_FILE, "run_model_training.py"),
    (config.DURATION_SCHEMA_FILE, "run_model_training.py"),
    (config.OPEN_APPLICATIONS_FILE, "the supplied project files"),
    (config.APPLICATION_DOCUMENTS_FILE, "the supplied project files"),
    (config.DOCS_DIRECTORY, "the supplied project files"),
    (os.path.join(config.VECTOR_STORE_DIRECTORY, config.VECTOR_STORE_FILE_NAME),
     "run_knowledge_indexing.py"),
    (config.APPLICATION_DATABASE_FILE, "run_database_setup.py"),
]


def main():
    """Start the service where the earlier stages have run; explain what is missing otherwise."""
    missing = [(path, source) for path, source in REQUIRED_BEFORE_STARTING
               if not os.path.exists(path)]
    if missing:
        print("The service cannot start.")
        for path, source in missing:
            print(f"  {path} is missing; it comes from {source}")
        return 1
    import uvicorn

    from api.routes import service_application

    print(f"Starting {config.API_TITLE} on port {config.API_PORT}.")
    print(f"Interactive documentation: {config.API_BASE_URL}/docs")
    uvicorn.run(service_application, host=config.API_HOST, port=config.API_PORT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
