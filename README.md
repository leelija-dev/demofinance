# Sundaram JS Bundling Setup

Your project uses ES6 JavaScript (with imports) and requires bundling for browser support. This setup uses [Vite](https://vitejs.dev/) for fast, modern bundling.

## How to Build Your JavaScript

1. **Install dependencies** (only needed once):
   ```sh
   npm install
   ```

2. **Build your JS for production:**
   ```sh
   npm run build
   ```
   This will bundle your JS from `static/js/index.js` and output the browser-ready bundle to `static/js/index.js` (overwriting the original).

3. **Development mode (auto-rebuild on changes):**
   ```sh
   npm run dev
   ```
   (You may need to adjust static file serving for dev mode.)

## Template Usage
Make sure your Django template includes:
```html
<script src="{% static 'js/index.js' %}"></script>
```

## Notes
- Do NOT reference ES6 source files directly in templates—always use the bundled output.
- If you add new npm packages, run `npm install <package>` and rebuild.

## Post Deployment Jobs/Seeders
- python manage.py seed_branch_permissions
- python manage.py seed_chart_of_accounts
- python manage.py setup_roles

## Verify the cron job is running
```sh
docker compose exec web crontab -l
```
## Check the cron logs:
```sh
docker compose exec web tail -f /var/log/cron.log
```
