# MLH PE Hackathon - Flask + Peewee + PostgreSQL Template

A Flask + Peewee scaffold with OmniGuard-integrated routes for health, CSV datasets, and upstream data access.

Stack: Flask - Peewee ORM - PostgreSQL - uv

## Important

Use the seed files from the MLH PE Hackathon platform to design your schema, load realistic data, and validate your submission workflows.

## Prerequisites

- uv installed: https://docs.astral.sh/uv/
- PostgreSQL running locally (Docker or local install)

## Quick Start

```bash
# 1) Install dependencies (creates .venv automatically)
uv sync

# 2) Create database (Windows PowerShell)
$env:PGPASSWORD = "your_postgres_password"
createdb -h localhost -U postgres hackathon_db
Remove-Item Env:PGPASSWORD

# 3) Configure environment
Copy-Item .env.example .env
# edit values if needed

# 4) Run server
uv run run.py

# 5) Verify
curl http://localhost:5000/health
# -> {"status":"ok"}

# 6) OmniGuard routes
curl http://localhost:5000/
curl "http://localhost:5000/api/data?source=csv&endpoint=/users&limit=5"
curl http://localhost:5000/api/csv/datasets
```

## Project Structure

```text
.
├── app/
│   ├── __init__.py          # Flask app factory (create_app)
│   ├── database.py          # DatabaseProxy, BaseModel, connect/close hooks
│   ├── models/
│   │   └── __init__.py      # Import your models here
│   ├── routes/
│   │   ├── __init__.py      # register_routes(app)
│   │   └── health.py        # Example /health blueprint
│   ├── main.py              # Existing OmniGuard FastAPI app (kept as legacy)
│   └── ...
├── .env.example             # PostgreSQL + Flask settings
├── .python-version          # Python version pin for uv
├── pyproject.toml           # Project metadata + dependencies
├── run.py                   # Entry point (uv run run.py)
└── README.md
```

## Add a Model

Create a model file, for example app/models/product.py:

```python
from peewee import CharField, DecimalField, IntegerField

from app.database import BaseModel


class Product(BaseModel):
    name = CharField()
    category = CharField()
    price = DecimalField(decimal_places=2)
    stock = IntegerField()
```

Then import it in app/models/__init__.py and create tables with a setup script.

## Add Routes

Create a blueprint under app/routes and register it in app/routes/__init__.py.

## CSV Loading Example

```python
import csv
from peewee import chunked

from app.database import db
from app.models.product import Product


def load_csv(filepath: str) -> None:
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    with db.atomic():
        for batch in chunked(rows, 100):
            Product.insert_many(batch).execute()
```

## Useful Peewee Patterns

```python
from peewee import fn
from playhouse.shortcuts import model_to_dict

# Select all
products = Product.select()

# Filter
cheap = Product.select().where(Product.price < 10)

# Aggregation
avg_price = Product.select(fn.AVG(Product.price)).scalar()
```

## Notes

- Legacy OmniGuard observability, load-testing, and docs files were kept in the repository.
- The primary hackathon scaffold entry point is run.py using Flask app factory.
