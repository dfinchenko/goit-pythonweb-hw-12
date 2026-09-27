"""Service health check."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.db import get_db

router = APIRouter(tags=["utils"])
logger = logging.getLogger(__name__)


@router.get("/healthchecker")
async def healthchecker(db: AsyncSession = Depends(get_db)):
    """Check that the API is up and the database answers ``SELECT 1``.

    Raises:
        HTTPException: 500 if the database is unreachable.
    """
    try:
        result = await db.execute(text("SELECT 1"))
        if result.scalar_one_or_none() != 1:
            raise RuntimeError("unexpected result")
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error connecting to the database",
        )
    return {"message": "Welcome to FastAPI!"}
