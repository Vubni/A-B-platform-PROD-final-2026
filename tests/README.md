# API-тесты

## Запуск

Локально (из корня проекта):

```bash
pip install -r backend/requirements.txt -r requirements-test.txt
export API_BASE_URL=http://localhost:80
python tests/seed_test_data.py
pytest
```

Только pytest (backend и сид уже есть):

```bash
export API_BASE_URL=http://localhost:80
pytest
```

Docker:

```bash
docker-compose --profile test run --rm --build tests
```

Отдельные модули:

```bash
pytest tests/test_health.py
pytest tests/test_flags_api.py
pytest tests/test_users_api.py
pytest tests/test_experiments_api.py
pytest tests/test_decide_api.py
```

## Переменные

| Переменная     | По умолчанию          |
|----------------|------------------------|
| `API_BASE_URL` | `http://localhost:80`  |
