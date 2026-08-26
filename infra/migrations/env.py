from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import model modules so they register their tables on Base.metadata
# before autogenerate/upgrade runs. Sprints add to this list as they
# introduce new `src/<package>/models.py` modules. Aliased so each import
# binds a distinct name -- otherwise ruff can't tell the separate
# `import src.<x>.models` statements apart (they all bind `src`).
from src.agent import models as _agent_models  # noqa: F401
from src.db import Base
from src.graph import models as _graph_models  # noqa: F401
from src.ingestion import models as _ingestion_models  # noqa: F401
from src.settings import get_settings
from src.validation import models as _validation_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
