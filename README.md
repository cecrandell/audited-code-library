# Audited Code Library

![CI](https://github.com/cecrandell/audited-code-library/actions/workflows/ci.yml/badge.svg)

## What does this application do and why?

A demo of a secure, auditable workflow for distributing scientific software.

Users request access to software packages. Administrators review and approve each request. The system records every action in an audit log, so it can always answer the question: who received which version of which package, and who approved it?

Scientific organisations often share specialised software with universities, labs, and industry. Some of this software has licence rules or export controls. Teams need a system that is secure, easy to use, and fully accountable. This project shows one way to build that system with Python and Django.

## Features

- [x] Catalogue of software packages with versions and checksums
- [x] Access requests from registered users
- [x] Admin review and approval workflow
- [x] Audit log for packages, versions, requests, and reviews
- [ ] Audit log for downloads
- [x] Automated tests
- [ ] REST API for packages and requests
- [x] Docker setup with PostgreSQL
- [x] CI pipeline (GitHub Actions)
- [ ] CD: publish Docker image

## Step-by-Step on how to set up the application

1. Open your Terminal and create your SSH keys:

```js
ssh-keygen -t ed25519 -C "<email associated with your GitHub account>"
ssh-add ~/.ssh/id_ed25519
pbcopy < ~/.ssh/id_ed25519.pub
```

2. On GitHub, go to **Settings > SSH and GPG keys > New SSH key**. Give it a title (for example, "MacBook"), paste the key, and save.

3. Then back to the Terminal to clone this application repository onto your computer. Navigate to where you would like to download the source code:

```js
git clone git@github.com:cecrandell/audited-code-library.git
cd audited-code-library
python3 -m venv .venv
source .venv/bin/activate
pip install django djangorestframework
pip freeze > requirements.txt
django-admin startproject config .
python manage.py startapp catalogue
```

2. Open [config/settings.py](/audited-code-library/config/settings.py), find `INSTALLED_APPS`, and add two lines at the end:

```js
    "rest_framework",
    "catalogue",
```

3. Create the database and an admin user:

```js
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

4. Open `http://127.0.0.1:8000/admin` and log in with your superuser account.

## Technologies Used

- Python 3.10 or newer (this project uses 3.12)
- Django 5.2 LTS
- Django REST Framework
- PostgreSQL
- Docker
- GitHub Actions for CI/CD

### Environment Variables

This project reads its settings from a `.env` file, so secrets never go into the code. Please use the `.env.example` file as a guide to creating your own `.env` file.

## Data model

| Model            | Purpose                                                        |
| ---------------- | -------------------------------------------------------------- |
| `Institution`    | The organisation that requests software, with its country code |
| `CodePackage`    | A piece of software. Restricted packages need extra review     |
| `PackageVersion` | One release of a package, with a SHA-256 checksum              |
| `AccessRequest`  | A user asks for one version. An admin approves or rejects it   |
| `AuditLog`       | A permanent, append-only record of every action                |

### Design decisions

- Foreign keys use `PROTECT`, so records with history cannot be deleted.
- A database check constraint makes sure every reviewed request records who reviewed it and when.
- Audit log entries cannot be changed or deleted through the app or the admin. In production, database permissions should also block UPDATE and DELETE on this table.
- Admins approve or reject requests with admin actions. Each action updates the request and writes an audit entry in one database transaction.
- Only pending requests can be reviewed, so every decision is final and traceable.
- `transaction.atomic()`: the status change and the audit entry save together, or neither saves. You can never have an approval with no record of it.
- `select_for_update()`: if two admins click Approve at the same moment, the database locks the rows, so one request cannot get reviewed twice.
- The status field is read-only in the admin. In testing, a manual status change with no reviewer was blocked by the database check constraint, which confirmed the constraint works as a final safeguard.
- Checksums: A checksum is a fingerprint for a file. You run the file through a function called SHA-256, and it gives you a code that is always 64 characters long, using only 0 to 9 and a to f. Change one letter in the file, and the whole fingerprint changes. So when someone downloads a package, they can make the fingerprint again and compare it. If the two match, the file is exactly the one you sent, with no damage and no tampering. To make a checksum, go to your Terminal:

```js
shasum -a 256 <filename>
```

Then make a change to your file and save. Run the command above again, and you should see a new code.

## Running tests

```js
python manage.py test
```

The tests check that:

- A package cannot have two versions with the same number.
- The database blocks an approved request with no reviewer.
- Audit log entries cannot be changed or deleted.
- Approve and reject actions set the reviewer and write one audit entry.
- A request cannot be reviewed twice.

## Run with Docker

This runs the app with PostgreSQL in containers.

1. Install Docker Desktop.
2. Copy `.env.example` to `.env` and fill in the values.
3. Start the app:

```js
   docker compose up --build
```

4. In a second terminal, create an admin user:

```js
   docker compose exec web python manage.py createsuperuser
```

5. Open http://localhost:8000/admin.

Run the tests against PostgreSQL:

```js
docker compose exec web python manage.py test
```

Without Docker, the app uses SQLite for quick local development.

## Continuous integration

GitHub Actions runs on every push and pull request:

1. Lints the code with Ruff.
2. Runs Django's system check.
3. Fails if a model change has no migration.
4. Runs the test suite against PostgreSQL 17.
5. Builds the Docker image.

## Developer

Caroline Crandell - cecrandell
