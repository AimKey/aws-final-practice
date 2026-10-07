import os

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

with create_engine(os.environ["DATABASE_URL"]).connect() as connection:
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()
