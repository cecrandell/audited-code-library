# Audited Code Library

## What does this application do and why?

A demo of a secure, auditable workflow for distributing scientific software.

Users request access to software packages. Administrators review and approve each request. The system records every action in an audit log, so it can always answer the question: who received which version of which package, and who approved it?

Scientific organisations often share specialised software with universities, labs, and industry. Some of this software has licence rules or export controls. Teams need a system that is secure, easy to use, and fully accountable. This project shows one way to build that system with Python and Django.

## Features

- [ ] Catalogue of software packages with versions and checksums
- [ ] Access requests from registered users
- [ ] Admin review and approval workflow
- [ ] Audit log for every action
- [ ] REST API for packages and requests
- [ ] Automated tests
- [ ] Docker setup
- [ ] CI/CD pipeline

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

### Environment variables

This project reads its settings from a `.env` file, so secrets never go into the code. Please use the `.env.example` file as a guide to creating your own `.env` file.

## Developer

Caroline Crandell - cecrandell
