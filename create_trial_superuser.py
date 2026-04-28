#!/usr/bin/env python
"""
Django Trial Superuser Creator
Creates a 7-day trial superuser account for demo purposes.
"""

import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django environment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()

from django.contrib.auth import get_user_model
from headquater.models import Role

def create_trial_superuser():
    """Create a 7-day trial superuser"""
    
    User = get_user_model()
    trial_email = "trial@demofinance.com"
    trial_username = "trial_admin"
    trial_password = "trial123456"
    
    # Check if trial user already exists
    if User.objects.filter(email=trial_email).exists():
        existing_user = User.objects.get(email=trial_email)
        print("❌ Trial user already exists!")
        print(f"   Email: {existing_user.email}")
        print(f"   Username: {existing_user.username}")
        
        if hasattr(existing_user, 'trial_expiry_date') and existing_user.trial_expiry_date:
            if existing_user.trial_expiry_date > datetime.now():
                days_left = (existing_user.trial_expiry_date - datetime.now()).days
                print(f"   🟢 Trial expires in: {days_left} days")
            else:
                print("   🔴 Trial has expired!")
        return False
    
    try:
        # Get or create Super Admin role
        super_admin_role, _ = Role.objects.get_or_create(
            name='Super Admin',
            defaults={'role_type': 'super_admin'}
        )
        
        # Create trial superuser
        trial_user = User.objects.create_user(
            username=trial_username,
            email=trial_email,
            password=trial_password,
            first_name='Trial',
            last_name='Admin',
            is_headquater_admin=True,
            is_staff=True,
            is_superuser=True,
            is_active=True
        )
        
        # Set trial expiry (7 days)
        trial_user.trial_expiry_date = datetime.now() + timedelta(days=7)
        trial_user.role = super_admin_role
        trial_user.save()
        
        print("✅ Trial superuser created!")
        print("=" * 40)
        print(f"📧 Email: {trial_email}")
        print(f"👤 Username: {trial_username}")
        print(f"🔑 Password: {trial_password}")
        print(f"📅 Expires: {trial_user.trial_expiry_date.strftime('%Y-%m-%d %H:%M')}")
        print("=" * 40)
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def list_trial_users():
    """List trial users status"""
    User = get_user_model()
    trial_users = User.objects.filter(email__contains='trial@')
    
    if not trial_users.exists():
        print("📭 No trial users found.")
        return
    
    print("📋 TRIAL USERS:")
    print("=" * 40)
    
    for user in trial_users:
        if hasattr(user, 'trial_expiry_date') and user.trial_expiry_date:
            if user.trial_expiry_date > datetime.now():
                days_left = (user.trial_expiry_date - datetime.now()).days
                status = f"🟢 {days_left} days left"
            else:
                status = "🔴 Expired"
        else:
            status = "❓ No expiry date"
        
        print(f"👤 {user.username}")
        print(f"   Status: {status}")
        print()

def cleanup_expired_trials():
    """Deactivate expired trial users"""
    User = get_user_model()
    
    expired_users = User.objects.filter(
        email__contains='trial@',
        trial_expiry_date__lt=datetime.now(),
        is_active=True
    )
    
    if not expired_users.exists():
        print("✅ No expired trial users.")
        return
    
    count = expired_users.count()
    expired_users.update(is_active=False)
    print(f"🧹 Deactivated {count} expired users.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "list":
            list_trial_users()
        elif command == "cleanup":
            cleanup_expired_trials()
        elif command == "create":
            create_trial_superuser()
        else:
            print("Usage: create|list|cleanup")
    else:
        create_trial_superuser()
