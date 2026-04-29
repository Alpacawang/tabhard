# Tabeasy
An automated tabulation website for mock trial tournaments available at [tabeasy.org](https://tabeasy.org/). Used by 5+ tournaments, 1000+ people. 

## Installation
This project now targets modern Python and Django:

- Python `3.13`
- Django `6.0.x`
- PostgreSQL via `psycopg`

1. Clone this repo.
```
git@github.com:carlguo866/tabeasy.git
```

2. Create and activate an environment.

Using conda:
```
conda env create -f env-mac.yaml 
conda activate tabeasy
```

Using `venv` instead:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Set up PostgreSQL and create credentials that match `tabeasy.settings.DATABASES`, or override them in your local secrets/settings.

4. Optional: create `tabeasy_secrets/secret.py` with deployment-specific values if you need custom secrets. The app now falls back to safe development defaults when that file is absent.

5. Run migrations and start the server.
```
python manage.py migrate
python manage.py runserver
```
