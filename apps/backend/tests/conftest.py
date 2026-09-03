"""Shared backend test fixtures."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kya_platform.config import Settings
from kya_platform.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    return Settings(environment="test", version="test-version")


@pytest.fixture
def app(test_settings: Settings) -> FastAPI:
    return create_app(test_settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
