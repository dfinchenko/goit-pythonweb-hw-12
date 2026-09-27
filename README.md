# goit-pythonweb-hw-12 — Contacts REST API

Фінальне ДЗ курсу Fullstack Web Development with Python (GoIT). REST API для зберігання контактів на **FastAPI + SQLAlchemy (async) + PostgreSQL + Redis**.

## Що реалізовано

| Вимога | Де в коді |
|---|---|
| Документація Sphinx (docstrings у всіх модулях) | `docs/`, збірка: `cd docs && make html` |
| Модульні тести репозиторіїв | `tests/unit/test_repository_*.py` |
| Інтеграційні тести маршрутів (pytest) | `tests/integration/` |
| Покриття тестами > 75% (pytest-cov) | зараз **99%** |
| Кешування поточного користувача в Redis | `src/services/cache.py`, `get_current_user` у `src/services/auth.py` |
| Скидання пароля через e-mail | `POST /api/auth/forgot_password` → лист → `POST /api/auth/reset_password` |
| Ролі `user` / `admin` | `UserRole`, `get_current_admin`; аватар змінює лише admin |
| *Додатково:* пара `access_token` + `refresh_token` | `POST /api/auth/login`, `/refresh` (ротація), `/logout` |
| Секрети лише в `.env` | `.env.example` — шаблон, `.env` у `.gitignore` |
| Docker Compose (app + PostgreSQL + Redis) | `docker-compose.yml`, `Dockerfile` |

### Деталі

- **Кеш користувача.** `get_current_user` спочатку читає користувача з Redis (`user:<username>`, TTL `USER_CACHE_TTL`), і лише при промаху звертається до БД. У кеш не потрапляють хеш пароля та refresh-токен. Кеш інвалідовується при зміні аватара, пароля, ролі, підтвердженні e-mail. Якщо Redis недоступний — застосунок працює через БД.
- **Скидання пароля.** Токен скидання живе `RESET_TOKEN_EXPIRE_MINUTES` хвилин і одноразовий (містить відбиток поточного хешу пароля — після зміни пароля він більше не валідний). Після скидання всі refresh-токени відкликаються. Відповідь `forgot_password` однакова для існуючих і неіснуючих e-mail. Посилання з листа відкриває просту HTML-форму для введення нового пароля.
- **Ролі.** При реєстрації роль завжди `user` (передати `admin` у запиті неможливо). Адміністратора створює команда `python -m src.create_admin <username> <email> <password>` (або підвищує існуючого користувача); далі admin може змінювати ролі через `PATCH /api/users/{id}/role`.
- **JWT.** Кожен токен має claim `type` (`access` / `refresh` / `email_verify` / `password_reset`), тож токен одного типу не можна використати замість іншого. Refresh-токен зберігається в БД і при кожному `/refresh` замінюється новим.

## Запуск через Docker Compose

```bash
cp .env.example .env        # заповнити паролі, JWT_SECRET, SMTP, Cloudinary
docker compose up --build
docker compose exec app python -m src.create_admin admin admin@example.com adminpass
```

Swagger: http://localhost:8000/docs

## Локальний запуск

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
docker compose up -d postgres redis
alembic upgrade head
uvicorn main:app --reload
```

## Тести та покриття

```bash
pytest --cov --cov-report=term-missing
```

Тести не потребують PostgreSQL/Redis: використовуються SQLite in-memory та `fakeredis`, відправка пошти й Cloudinary замокані.

## Документація

```bash
cd docs && make html        # результат: docs/_build/html/index.html
```

## Основні ендпоінти

| Метод | Шлях | Доступ |
|---|---|---|
| POST | `/api/auth/register` | всі |
| POST | `/api/auth/login` | всі (form: username, password) |
| POST | `/api/auth/refresh` · `/api/auth/logout` | refresh token |
| GET | `/api/auth/confirmed_email/{token}` | посилання з листа |
| POST | `/api/auth/request_email` | всі |
| POST | `/api/auth/forgot_password` · `/api/auth/reset_password` | всі |
| GET | `/api/users/me` | user (≤ 10 запитів/хв) |
| PATCH | `/api/users/avatar` | **admin** |
| PATCH | `/api/users/{id}/role` | **admin** |
| GET/POST | `/api/contacts/` | user |
| GET/PATCH/DELETE | `/api/contacts/{id}` | user (лише власні контакти) |
| GET | `/api/contacts/birthdays?days=7` | user |
| GET | `/api/healthchecker` | всі |
