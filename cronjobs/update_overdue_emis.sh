#!/bin/bash
# This script will be executed inside the container

# Wait for database to be ready
python manage.py wait_for_db

# Run the update_overdue_emis command
python manage.py update_overdue_emis --tz=Asia/Kolkata

echo "[$(date)] - Update overdue EMIs job completed"
