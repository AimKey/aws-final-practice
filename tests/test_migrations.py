from alembic.config import Config
from alembic.script import ScriptDirectory


def test_single_migration_head():
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    assert len(script.get_heads()) == 1
