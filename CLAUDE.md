# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Odoo 17.0 — a Python/PostgreSQL web ERP. The entry point is the `odoo-bin` script at the repo root. The server is configured via `odoo.conf` (local config; already present).

## Running the server

PostgreSQL is installed locally beside this repo at `D:\University\knowledgeManagementSystem\Postgres`.
The active data directory is `D:\University\knowledgeManagementSystem\Postgres\data`.
PostgreSQL must be running before Odoo.

```powershell
# 1. Start PostgreSQL
cd D:\University\knowledgeManagementSystem\Postgres
.\bin\pg_ctl.exe -D .\data -l .\data\log\postgresql.log start

# 2. Activate the venv
cd D:\University\knowledgeManagementSystem\odoo-test
.\venv\Scripts\Activate.ps1

# 3. Start Odoo
python odoo-bin -c odoo.conf
```

To stop PostgreSQL:
```powershell
cd D:\University\knowledgeManagementSystem\Postgres
.\bin\pg_ctl.exe -D .\data stop
```

The local config (`odoo.conf`) connects to PostgreSQL on `localhost:5432`, database `TripleHandT`, user/password `odoo/odoo`, and serves on port `8069`.

## Running tests

```powershell
# Run all tests for a module
python odoo-bin -c odoo.conf --test-enable -u <module_name> --stop-after-init

# Run a specific test class or method (using tag selector)
python odoo-bin -c odoo.conf --test-enable --test-tags <module_name>.<ClassName>.<method_name> --stop-after-init

# Run tests without a database (unit tests only)
python odoo-bin --test-enable --test-tags <module_name> --stop-after-init --no-http
```

## Installing dependencies

```powershell
# Windows
pip install -r requirements-win.txt

# Linux/Mac
pip install -r requirements.txt
```

## Architecture

### Core (`odoo/`)

- `odoo/models.py` — `BaseModel`, the ORM base class. All Odoo models inherit from `Model`, `TransientModel`, or `AbstractModel`.
- `odoo/api.py` — `Environment` (registry + cursor + user context), and decorators: `@api.model`, `@api.depends`, `@api.constrains`, `@api.onchange`.
- `odoo/fields.py` — field descriptors (`Char`, `Many2one`, `One2many`, `Many2many`, etc.).
- `odoo/http.py` — WSGI layer, `@route` decorator for HTTP controllers.
- `odoo/modules/` — module loading, dependency graph, registry, migration.
- `odoo/tests/common.py` — base test classes (`TransactionCase`, `SavepointCase`, `HttpCase`).

### Addons (`addons/`)

Each subdirectory is an Odoo module. Module structure:

```
addons/<module>/
  __manifest__.py   # metadata: name, depends, data files, assets
  __init__.py       # imports models, controllers
  models/           # Python model definitions
  views/            # XML view definitions
  data/             # XML/CSV data loaded on install
  security/         # ir.model.access.csv, record rules
  controllers/      # HTTP route handlers
  static/           # JS/CSS/images (served at /web/static/...)
  tests/            # test classes
  wizard/           # transient models + views for dialogs
  i18n/             # .po translation files
```

### ORM patterns

- Models are registered by `_name = 'module.model'` on the class; the ORM merges all classes with the same `_name` across modules (inheritance via `_inherit`).
- `env['model.name']` returns a recordset; `.browse(ids)`, `.search(domain)`, `.create(vals)` are the primary access methods.
- Computed fields declare `@api.depends(...)` and a `_compute_*` method; stored computed fields write back to the DB.
- `@api.constrains` raises `ValidationError`; `@api.onchange` returns UI feedback only (never persisted directly).

### Request lifecycle

HTTP requests go through `odoo/http.py` → route dispatch → controller method → ORM calls → PostgreSQL. The `env` object (Environment) binds a database cursor, the current user's ID, and a context dict throughout a request.

## Linting

```powershell
# flake8 is configured in setup.cfg
flake8 odoo/ addons/<module>/
```
