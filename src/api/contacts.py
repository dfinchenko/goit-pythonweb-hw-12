"""Contacts CRUD, search and upcoming birthdays."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.db import get_db
from src.database.models import User
from src.schemas import ContactCreate, ContactResponse, ContactUpdate
from src.services.auth import get_current_user
from src.services.contacts import ContactService

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("/birthdays", response_model=list[ContactResponse])
async def upcoming_birthdays(
    days: int = Query(7, ge=1, le=366),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Contacts whose birthday is within the next ``days`` days (7 by default)."""
    return await ContactService(db).get_upcoming_birthdays(user, days)


@router.get("/", response_model=list[ContactResponse])
async def list_contacts(
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List the current user's contacts with optional search filters."""
    return await ContactService(db).get_contacts(
        user,
        skip=skip,
        limit=limit,
        first_name=first_name,
        last_name=last_name,
        email=email,
    )


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get one contact by id (404 if it does not exist or belongs to someone else)."""
    return await ContactService(db).get_contact(contact_id, user)


@router.post("/", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    body: ContactCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a contact (409 if the e-mail or phone is already used)."""
    return await ContactService(db).create_contact(body, user)


@router.patch("/{contact_id}", response_model=ContactResponse)
@router.put("/{contact_id}", response_model=ContactResponse, include_in_schema=False)
async def update_contact(
    contact_id: int,
    body: ContactUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update the provided fields of a contact."""
    return await ContactService(db).update_contact(contact_id, body, user)


@router.delete("/{contact_id}", response_model=ContactResponse)
async def delete_contact(
    contact_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a contact and return it."""
    return await ContactService(db).remove_contact(contact_id, user)
