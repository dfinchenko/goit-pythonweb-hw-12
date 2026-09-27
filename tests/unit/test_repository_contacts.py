"""Unit tests for ContactRepository (database session is mocked)."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Contact, User
from src.repository.contacts import ContactRepository, _next_birthday
from src.schemas import ContactCreate, ContactUpdate


@pytest.fixture
def session():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def repo(session):
    return ContactRepository(session)


@pytest.fixture
def user():
    return User(id=1, username="alice")


def make_contact(**kw) -> Contact:
    data = dict(
        id=1,
        first_name="John",
        last_name="Doe",
        email="john@example.com",
        phone="+380501112233",
        birthday=date(1990, 5, 20),
        user_id=1,
    )
    data.update(kw)
    return Contact(**data)


def result_with(scalars=None, one=None):
    result = MagicMock()
    result.scalars.return_value.all.return_value = scalars or []
    result.scalars.return_value.first.return_value = (scalars or [None])[0]
    result.scalar_one_or_none.return_value = one
    return result


async def test_get_contacts_with_filters(repo, session, user):
    session.execute.return_value = result_with([make_contact()])
    contacts = await repo.get_contacts(
        user, skip=0, limit=10, first_name="jo", last_name="do", email="ex"
    )
    assert [c.first_name for c in contacts] == ["John"]
    stmt = str(session.execute.call_args[0][0]).lower()
    assert "like" in stmt and "user_id" in stmt


async def test_get_contact_by_id(repo, session, user):
    session.execute.return_value = result_with(one=make_contact())
    contact = await repo.get_contact_by_id(1, user)
    assert contact.email == "john@example.com"


async def test_create_contact(repo, session, user):
    body = ContactCreate(
        first_name="Jane",
        last_name="Roe",
        email="jane@example.com",
        phone="+380501112244",
        birthday=date(1992, 1, 2),
    )
    contact = await repo.create_contact(body, user)
    assert contact.first_name == "Jane" and contact.user_id == user.id
    session.add.assert_called_once()
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(contact)


async def test_update_contact(repo, session, user):
    existing = make_contact()
    session.execute.return_value = result_with(one=existing)
    updated = await repo.update_contact(1, ContactUpdate(first_name="Johnny"), user)
    assert updated.first_name == "Johnny"
    assert updated.last_name == "Doe"  # untouched field
    session.commit.assert_awaited_once()


async def test_update_contact_not_found(repo, session, user):
    session.execute.return_value = result_with(one=None)
    assert await repo.update_contact(9, ContactUpdate(first_name="X"), user) is None
    session.commit.assert_not_awaited()


async def test_remove_contact(repo, session, user):
    existing = make_contact()
    session.execute.return_value = result_with(one=existing)
    assert await repo.remove_contact(1, user) is existing
    session.delete.assert_awaited_once_with(existing)
    session.commit.assert_awaited_once()


async def test_remove_contact_not_found(repo, session, user):
    session.execute.return_value = result_with(one=None)
    assert await repo.remove_contact(9, user) is None
    session.delete.assert_not_awaited()


async def test_find_duplicate(repo, session, user):
    dup = make_contact()
    session.execute.return_value = result_with([dup])
    assert await repo.find_duplicate(user, "john@example.com", None, exclude_id=5) is dup


async def test_find_duplicate_without_values(repo, session, user):
    assert await repo.find_duplicate(user, None, None) is None
    session.execute.assert_not_awaited()


async def test_upcoming_birthdays_sorted_and_wraps_year(repo, session, user):
    today = date(2026, 12, 28)
    contacts = [
        make_contact(id=1, birthday=date(1990, 1, 2)),  # in 5 days, next year
        make_contact(id=2, birthday=date(1985, 12, 29)),  # tomorrow
        make_contact(id=3, birthday=date(2000, 6, 1)),  # far away
    ]
    session.execute.return_value = result_with(contacts)
    result = await repo.get_upcoming_birthdays(user, days=7, today=today)
    assert [c.id for c in result] == [2, 1]


def test_next_birthday_leap_day():
    assert _next_birthday(date(2000, 2, 29), date(2027, 2, 1)) == date(2027, 2, 28)
    assert _next_birthday(date(2000, 2, 29), date(2028, 2, 1)) == date(2028, 2, 29)
    assert _next_birthday(date(1990, 3, 1), date(2026, 3, 2)) == date(2027, 3, 1)
