"""Integration tests for the health check and rate limiter."""

from unittest.mock import AsyncMock

from main import app
from src.database.db import get_db
from src.services.limiter import limiter


async def test_healthchecker(client):
    resp = await client.get("/api/healthchecker")
    assert resp.status_code == 200
    assert resp.json() == {"message": "Welcome to FastAPI!"}


async def test_healthchecker_db_error(client):
    async def broken_db():
        session = AsyncMock()
        session.execute.side_effect = Exception("db down")
        yield session

    app.dependency_overrides[get_db] = broken_db
    resp = await client.get("/api/healthchecker")
    assert resp.status_code == 500


async def test_rate_limit_on_me(client, user_headers):
    limiter.enabled = True
    limiter.reset()
    try:
        codes = [
            (await client.get("/api/users/me", headers=user_headers)).status_code
            for _ in range(11)
        ]
    finally:
        limiter.enabled = False
    assert codes[:10] == [200] * 10
    assert codes[10] == 429
