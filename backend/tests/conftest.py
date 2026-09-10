import pytest
from app.persistence import Repository
from app.engine import SimulationEngine


@pytest.fixture
def repository(tmp_path):
    repo = Repository(f"sqlite:///{tmp_path / 'test.db'}")
    yield repo
    repo.engine.dispose()


@pytest.fixture
async def engine(repository):
    value = SimulationEngine(repository)
    yield value
    await value.close()
