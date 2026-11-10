# PhaseWise AI - project code (52 files)

The same files the Team Planner shows, in their folders. Copy them into your `Project` folder
(next to the pre-loaded `config/`, `data/`, `.env`, `.streamlit/` and `requirements.txt` - none of those are replaced).

Run from the Project folder, in this order:

    pip install -r requirements.txt
    python run_database_setup.py
    python run_data_pipeline.py
    python run_model_training.py
    python run_knowledge_indexing.py
    python run_api_service.py                 # terminal 2, leave running (port 8081)
    python -m streamlit run run_dashboard.py  # terminal 3 (port 8080)
    python -m pytest tests.py -q              # start from an empty database: delete database/phasewise.db and database/checkpoint.db first

`.env` must hold GEMINI_API_KEY and GEMINI_MODEL for the review workflow and the chat.
No __init__.py files are needed: the folders are imported as namespace packages from the Project folder.
