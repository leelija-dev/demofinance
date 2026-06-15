#!/bin/bash
# This script will be executed inside the container

# Wait for database to be ready
python manage.py wait_for_db

# Run the clear_trial_headquater_user_data command
python manage.py clear_trial_headquater_user_data --tz=Asia/Kolkata

echo "[$(date)] - Clear trial HQ user data job completed"