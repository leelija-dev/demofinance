# Django Dev Server Fix - Postgres Connection Issue

## Approved Plan Steps
[x] 1. Updated TODO.md with correct DB name & steps
[ ] 2. Update .env: DBNAME=demofinance (keep DATABASE=postgresql)
[ ] 3. Ensure Postgres running with 'demofinance' DB on localhost:5432 (per POSTGRES_WINDOWS_SETUP.md)
[ ] 4. python manage.py makemigrations
[ ] 5. python manage.py migrate
[ ] 6. python manage.py runserver
[ ] 7. Verify http://127.0.0.1:8000/

Status: Awaiting Postgres setup confirmation. Quick SQLite alternative available.

