import os

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg2://", 1)

with create_engine(url).connect() as connection:
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()
