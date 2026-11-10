"""The one connection to the application database and the session factory.

Both are built once, on import. Importing creates no table and writes nothing;
run_database_setup.py creates the tables.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import config

# The web framework answers on threads of its own, so the connection is shared
# across threads; a generous timeout lets concurrent writers wait their turn.
database_engine = create_engine(
    config.APPLICATION_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 60},
)

session_factory = sessionmaker(bind=database_engine, expire_on_commit=False)
