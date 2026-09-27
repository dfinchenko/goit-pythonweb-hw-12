"""Shared ``slowapi`` rate limiter."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from src.conf.config import settings

limiter = Limiter(key_func=get_remote_address, enabled=settings.RATE_LIMIT_ENABLED)
