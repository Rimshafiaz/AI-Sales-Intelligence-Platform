from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.db.session import engine

EXPECTED_TABLES = {
    "users",
    "companies",
    "research_requests",
    "research_sources",
    "research_reports",
    "alembic_version",
}


class TestMigrations:
    def test_all_expected_tables_exist(self):
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert EXPECTED_TABLES.issubset(tables)

    def test_database_is_at_migration_head(self):
        config = AlembicConfig("alembic.ini")
        script_directory = ScriptDirectory.from_config(config)
        head_revision = script_directory.get_current_head()

        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_revision = context.get_current_revision()

        assert current_revision == head_revision
