"""Data access layer for contacts."""

from datetime import date, timedelta
from typing import Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Contact, User
from src.schemas import ContactCreate, ContactUpdate


def _next_birthday(birthday: date, today: date) -> date:
    """Return the next date (today or later) on which ``birthday`` is celebrated.

    People born on 29 February celebrate on 28 February in non-leap years.

    Args:
        birthday: Date of birth.
        today: Reference date.

    Returns:
        date: The nearest upcoming birthday.
    """
    for year in (today.year, today.year + 1):
        try:
            candidate = birthday.replace(year=year)
        except ValueError:  # 29 Feb in a non-leap year
            candidate = date(year, 2, 28)
        if candidate >= today:
            return candidate
    raise AssertionError("unreachable")  # pragma: no cover


class ContactRepository:
    """CRUD operations for :class:`~src.database.models.Contact`.

    Every query is scoped to the owner, so a user can never read or modify
    another user's contacts.

    Args:
        session: An open async database session.
    """

    def __init__(self, session: AsyncSession):
        self.db = session

    async def get_contacts(
        self,
        user: User,
        skip: int = 0,
        limit: int = 100,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
    ) -> Sequence[Contact]:
        """Return a page of the user's contacts, optionally filtered.

        Filters are case-insensitive substring matches.

        Args:
            user: Owner of the contacts.
            skip: Number of records to skip.
            limit: Maximum number of records to return.
            first_name: Filter by first name.
            last_name: Filter by last name.
            email: Filter by e-mail.

        Returns:
            Sequence[Contact]: Matching contacts.
        """
        stmt = select(Contact).where(Contact.user_id == user.id)
        if first_name:
            stmt = stmt.where(Contact.first_name.ilike(f"%{first_name}%"))
        if last_name:
            stmt = stmt.where(Contact.last_name.ilike(f"%{last_name}%"))
        if email:
            stmt = stmt.where(Contact.email.ilike(f"%{email}%"))
        stmt = stmt.order_by(Contact.id).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_contact_by_id(self, contact_id: int, user: User) -> Contact | None:
        """Return one contact of the user by id.

        Args:
            contact_id: Contact id.
            user: Owner of the contact.

        Returns:
            Contact | None: The contact or ``None`` if not found.
        """
        stmt = select(Contact).where(
            Contact.id == contact_id, Contact.user_id == user.id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_duplicate(
        self,
        user: User,
        email: str | None,
        phone: str | None,
        exclude_id: int | None = None,
    ) -> Contact | None:
        """Find a user's contact that already has the given e-mail or phone.

        Args:
            user: Owner of the contacts.
            email: E-mail to look for.
            phone: Phone to look for.
            exclude_id: Contact id to ignore (used on update).

        Returns:
            Contact | None: The conflicting contact, if any.
        """
        conditions = []
        if email:
            conditions.append(Contact.email == email)
        if phone:
            conditions.append(Contact.phone == phone)
        if not conditions:
            return None
        stmt = select(Contact).where(Contact.user_id == user.id, or_(*conditions))
        if exclude_id is not None:
            stmt = stmt.where(Contact.id != exclude_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def create_contact(self, body: ContactCreate, user: User) -> Contact:
        """Create a contact for the user.

        Args:
            body: Contact data.
            user: Owner of the new contact.

        Returns:
            Contact: The created contact.
        """
        contact = Contact(**body.model_dump(), user_id=user.id)
        self.db.add(contact)
        await self.db.commit()
        await self.db.refresh(contact)
        return contact

    async def update_contact(
        self, contact_id: int, body: ContactUpdate, user: User
    ) -> Contact | None:
        """Update the provided fields of a user's contact.

        Args:
            contact_id: Contact id.
            body: Fields to update (unset fields are ignored).
            user: Owner of the contact.

        Returns:
            Contact | None: The updated contact or ``None`` if not found.
        """
        contact = await self.get_contact_by_id(contact_id, user)
        if contact is None:
            return None
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(contact, field, value)
        await self.db.commit()
        await self.db.refresh(contact)
        return contact

    async def remove_contact(self, contact_id: int, user: User) -> Contact | None:
        """Delete a user's contact.

        Args:
            contact_id: Contact id.
            user: Owner of the contact.

        Returns:
            Contact | None: The deleted contact or ``None`` if not found.
        """
        contact = await self.get_contact_by_id(contact_id, user)
        if contact is None:
            return None
        await self.db.delete(contact)
        await self.db.commit()
        return contact

    async def get_upcoming_birthdays(
        self, user: User, days: int = 7, today: date | None = None
    ) -> list[Contact]:
        """Return contacts whose birthday falls within the next ``days`` days.

        The calculation handles the year boundary and 29 February, and the
        result is sorted by the nearest birthday first.

        Args:
            user: Owner of the contacts.
            days: Size of the window in days (today included).
            today: Reference date, defaults to the current date.

        Returns:
            list[Contact]: Contacts with upcoming birthdays.
        """
        today = today or date.today()
        end = today + timedelta(days=days)
        result = await self.db.execute(
            select(Contact).where(Contact.user_id == user.id)
        )
        upcoming = [
            (_next_birthday(c.birthday, today), c) for c in result.scalars().all()
        ]
        return [c for bday, c in sorted(upcoming, key=lambda x: x[0]) if bday <= end]
