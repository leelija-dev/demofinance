# Trial Superuser System

7-day trial superuser with automatic logout.

## Usage

```bash
# Create trial user
python create_trial_superuser.py

# List trial users
python create_trial_superuser.py list

# Clean expired users
python create_trial_superuser.py cleanup
```

## Login Credentials
- **Email**: trial@demofinance.com
- **Username**: trial_admin  
- **Password**: trial123456

## How It Works
- Creates 7-day trial superuser
- Middleware checks expiry on each request
- Auto-logout when expired
- User deactivated after expiry

## Files
- `create_trial_superuser.py` - Management script
- `headquater/middleware.py` - Auto-logout middleware
- `headquater/migrations/0004_headquarteremployee_trial_expiry_date.py` - DB migration

## Setup
1. Run migrations: `python manage.py migrate`
2. Create trial user: `python create_trial_superuser.py`
3. Login at: `/hq/login/`
