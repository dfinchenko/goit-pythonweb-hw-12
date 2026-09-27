"""FastAPI application entry point."""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from src.api import auth, contacts, users, utils
from src.services.limiter import limiter

app = FastAPI(
    title="Contacts API",
    description="REST API for storing contacts with JWT auth, roles and Redis cache.",
    version="1.0.0",
)
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Return 429 when a client exceeds the rate limit."""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Too many requests. Try again later."},
    )


app.include_router(utils.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(contacts.router, prefix="/api")


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
