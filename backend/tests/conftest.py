import os
import tempfile
from pathlib import Path

# Set these before importing the application; tests never touch the demo database.
_work = Path(__file__).resolve().parents[2] / 'work'
_work.mkdir(exist_ok=True)
_temporary = tempfile.TemporaryDirectory(prefix='water-guardian-tests-', dir=_work, ignore_cleanup_errors=True)
TEST_ROOT = Path(_temporary.name)
os.environ['DATABASE_URL'] = 'sqlite:///' + (TEST_ROOT / 'test.db').as_posix()
os.environ['WORKFLOW_DATABASE_PATH'] = str(TEST_ROOT / 'checkpoints.db')
os.environ['ML_MODEL_PATH'] = str(TEST_ROOT / 'monitor.joblib')
os.environ['ML_EVALUATION_PATH'] = str(TEST_ROOT / 'evaluation.json')

import pytest
from fastapi.testclient import TestClient
from backend.app import main
from backend.app.db import Base, engine


@pytest.fixture
def client(monkeypatch):
    Base.metadata.drop_all(engine)
    main.replay.running = False
    main.replay.error = None
    main.decision_locks.clear()
    main.monitor.bundle = None
    main.monitor.error = None
    # Keep integration tests deterministic and avoid any real paid API requests.
    monkeypatch.setattr('backend.app.workflow.router.structured',
        lambda task, payload, schema, fallback: (schema.model_validate(fallback).model_dump(), 'evidence_only', []))
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def test_root():
    return TEST_ROOT
