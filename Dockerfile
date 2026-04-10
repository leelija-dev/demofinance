# Build stage for Node.js dependencies
FROM node:22.9.0-alpine as node-build

WORKDIR /app

# Copy package files
COPY package*.json ./
COPY tailwind.config.js ./
COPY postcss.config.cjs ./
COPY vite.config.js ./

# Install Node.js dependencies
RUN npm install

# Copy static files
COPY static/ ./static/

# Build static files
RUN npm run build

# Final stage for Python/Django
# Use a stable Python version with wide wheel support
# FROM python:3.12-slim
FROM python:3.12-slim AS stage-1

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SECRET_KEY=change-me \
    DEBUG=False

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*


RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgobject-2.0-0 \
    libnspr4 \
    libnss3 \
    libgio-2.0-0 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libexpat1 \
    libxcb1 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libcairo2 \
    libpango-1.0-0 \
    libasound2 \
    fonts-unifont \
 && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m playwright install chromium
# Copy project
COPY . .

# Copy built static files from node-build stage
COPY --from=node-build /app/static /app/static

# Collect static files
RUN python manage.py collectstatic --noinput

# Install cron and other required packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Create log file for cron
RUN touch /var/log/cron.log

# Copy cron files
COPY cronjobs/update_overdue_emis.sh /app/cronjobs/
RUN chmod +x /app/cronjobs/update_overdue_emis.sh

# Copy crontab file and set permissions
COPY cronjobs/crontab /etc/cron.d/update-overdue-emis
RUN chmod 0644 /etc/cron.d/update-overdue-emis && \
    # Ensure the file has the correct line endings
    sed -i 's/\r$//' /etc/cron.d/update-overdue-emis && \
    # Ensure the file ends with a newline
    echo >> /etc/cron.d/update-overdue-emis && \
    # Install the crontab
    crontab /etc/cron.d/update-overdue-emis || true

# Expose the port the app runs on
EXPOSE 8000

# Command to run the ASGI application via Uvicorn worker
CMD ["gunicorn", "main.asgi:application", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
