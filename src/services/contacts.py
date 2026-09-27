"""Business logic for contacts."""

from typing import Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Contact, User
from src.repository.contacts import ContactRepository
from src.schemas import ContactCreate, ContactUpdate


class ContactService:
    """Contact operations with ownership and duplicate checks.

    Args:
        db: An open async database session.
    """

    def __init__(self, db: AsyncSession):
        self.repository = ContactRepository(db)

    async def _ensure_unique(
        self, user: User, email: str | None, phone: str | None, exclude_id=None
    ) -> None:
        if await self.repository.find_duplicate(user, email, phone, exclude_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Contact with this email or phone already exists",
            )

    async def create_contact(self, body: ContactCreate, user: User) -> Contact:
        """Create a contact.

        Raises:
            HTTPException: 409 if e-mail or phone is already used by another contact.
        """
        await self._ensure_unique(user, body.email, body.phone)
        return await self.repository.create_contact(body, user)

    async def get_contacts(self, user: User, **filters) -> Sequence[Contact]:
        """Return the user's contacts (see :meth:`ContactRepository.get_contacts`)."""
        return await self.repository.get_contacts(user, **filters)

    async def get_contact(self, contact_id: int, user: User) -> Contact:
        """Return a contact.

        Raises:
            HTTPException: 404 if the contact does not exist.
        """
        contact = await self.repository.get_contact_by_id(contact_id, user)
        if contact is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Contact not found")
        return contact

    async def update_contact(
        self, contact_id: int, body: ContactUpdate, user: User
    ) -> Contact:
        """Partially update a contact.

        Raises:
            HTTPException: 404 if not found, 409 on duplicate e-mail / phone.
        """
        await self.get_contact(contact_id, user)
        await self._ensure_unique(user, body.email, body.phone, exclude_id=contact_id)
        return await self.repository.update_contact(contact_id, body, user)

    async def remove_contact(self, contact_id: int, user: User) -> Contact:
        """Delete a contact.

        Raises:
            HTTPException: 404 if the contact does not exist.
        """
        contact = await self.repository.remove_contact(contact_id, user)
        if contact is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Contact not found")
        return contact

    async def get_upcoming_birthdays(self, user: User, days: int) -> list[Contact]:
        """Return contacts with a birthday in the next ``days`` days."""
        return await self.repository.get_upcoming_birthdays(user, days)
