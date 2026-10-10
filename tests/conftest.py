import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.db import init_db  # noqa: E402
from database.repository import Repository  # noqa: E402


@pytest.fixture
def repo(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    return Repository(db)


@pytest.fixture
def pid(repo):
    return repo.create_profile("Tester")
