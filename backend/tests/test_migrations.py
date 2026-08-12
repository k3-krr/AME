import pytest
import uuid
import sqlalchemy as sa
from alembic.config import Config
from alembic import command
from app.config import settings


def test_alembic_migrations_workflow():
    """
    Integration test verifying database migrations workflow on an isolated PostgreSQL database.
    1. Setup: Create a temporary PostgreSQL database.
    2. Run upgrade to head.
    3. Verify tables are successfully created.
    4. Run downgrade to base.
    5. Verify tables are successfully dropped.
    6. Run upgrade to head again.
    7. Teardown: Drop the temporary database.
    """
    # 1. Parse database connection parameters
    base_url, db_name = settings.SYNC_DATABASE_URL.rsplit('/', 1)
    # Replace localhost with 127.0.0.1 to bypass Windows IPv6 loopback resolution issues with WSL
    base_url = base_url.replace("localhost", "127.0.0.1")
    admin_url = f"{base_url}/postgres"

    # Connect to admin DB and verify if PostgreSQL is available, else skip
    try:
        admin_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
    except Exception as e:
        pytest.skip(f"PostgreSQL server not available at {admin_url}. Skipping isolated migration test. Error: {e}")

    temp_db_name = f"temp_migration_test_db_{uuid.uuid4().hex}"

    with admin_engine.connect() as conn:
        conn.execute(sa.text(f"CREATE DATABASE {temp_db_name}"))

    temp_db_url = f"{base_url}/{temp_db_name}"

    # 2. Store original database URLs
    orig_sync_url = settings.SYNC_DATABASE_URL
    orig_async_url = settings.DATABASE_URL

    # Update configuration
    settings.SYNC_DATABASE_URL = temp_db_url
    settings.DATABASE_URL = temp_db_url.replace("postgresql://", "postgresql+asyncpg://")

    try:
        # 3. Run migrations upgrade to head
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")

        # Verify tables are created by connecting to the temp database
        temp_engine = sa.create_engine(temp_db_url)
        with temp_engine.connect() as conn:
            inspector = sa.inspect(temp_engine)
            tables = inspector.get_table_names()
            assert "users" in tables
            assert "memories" in tables
            assert "agents" in tables
            assert "memory_access_grants" in tables
            assert "memory_embeddings" in tables
            assert "kg_nodes" in tables
            assert "kg_relationships" in tables
        temp_engine.dispose()

        # 4. Run downgrade to base
        command.downgrade(alembic_cfg, "base")

        # Verify tables are dropped
        temp_engine = sa.create_engine(temp_db_url)
        with temp_engine.connect() as conn:
            inspector = sa.inspect(temp_engine)
            tables = inspector.get_table_names()
            assert "memories" not in tables
            assert "agents" not in tables
        temp_engine.dispose()

        # 5. Run upgrade to head again
        command.upgrade(alembic_cfg, "head")

        # Verify tables exist again
        temp_engine = sa.create_engine(temp_db_url)
        with temp_engine.connect() as conn:
            inspector = sa.inspect(temp_engine)
            tables = inspector.get_table_names()
            assert "memories" in tables
            assert "agents" in tables
        temp_engine.dispose()

    finally:
        # Restore configuration
        settings.SYNC_DATABASE_URL = orig_sync_url
        settings.DATABASE_URL = orig_async_url

        # Drop the temporary database
        with admin_engine.connect() as conn:
            # Terminate active connections first to allow drop
            conn.execute(sa.text(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{temp_db_name}'
                  AND pid <> pg_backend_pid()
            """))
            conn.execute(sa.text(f"DROP DATABASE {temp_db_name}"))
        admin_engine.dispose()
