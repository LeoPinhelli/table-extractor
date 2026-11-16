"""Isola os temporarios sem acessar diretorios de outras execucoes do pytest."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


def pytest_configure(config: pytest.Config) -> None:
    # Uma escolha explicita do usuario continua tendo prioridade.
    if config.option.basetemp is not None:
        return

    # mkdtemp cria uma pasta nova; nao enumera pytest-of-<usuario>, que pode
    # pertencer a outro contexto de permissao no Windows.
    temporary = TemporaryDirectory(prefix="table-extractor-tests-", ignore_cleanup_errors=True)
    # O pytest pode limpar basetemp antes de usa-lo. Por isso ele recebe um
    # filho ainda inexistente da pasta exclusiva que acabamos de criar.
    config.option.basetemp = str(Path(temporary.name) / "work")
    config.add_cleanup(temporary.cleanup)
