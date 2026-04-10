# PostgreSQL Windows Setup for Docker Connection

This guide will help you configure PostgreSQL on Windows to accept connections from Docker containers.

## Problem

Docker containers cannot connect to PostgreSQL running on Windows host because:
1. PostgreSQL may only be listening on `localhost` (127.0.0.1)
2. PostgreSQL's `pg_hba.conf` may not allow connections from Docker network
3. Windows Firewall may be blocking connections

## Solution Steps

### Step 1: Find PostgreSQL Configuration Directory

PostgreSQL configuration files are typically located in:
- **Default location**: `C:\Program Files\PostgreSQL\<version>\data\`
- Or check PostgreSQL service properties to find data directory

### Step 2: Configure PostgreSQL to Listen on All Interfaces

1. Open `postgresql.conf` in the PostgreSQL data directory
2. Find the line: `#listen_addresses = 'localhost'`
3. Change it to: `listen_addresses = '*'`
4. Save the file
5. Restart PostgreSQL service:
   ```powershell
   # Run PowerShell as Administrator
   Restart-Service postgresql-x64-<version>
   # Or use Services.msc GUI
   ```

### Step 3: Update pg_hba.conf to Allow Docker Connections

1. Open `pg_hba.conf` in the PostgreSQL data directory
2. Add these lines at the end of the file:

```
# Allow Docker containers to connect
host    all             all             172.16.0.0/12           md5
host    all             all             192.168.0.0/16          md5
host    all             all             10.0.0.0/8               md5
```

**Explanation:**
- `172.16.0.0/12` - Docker's default bridge network range
- `192.168.0.0/16` - Common private network range (includes Docker Desktop's network)
- `10.0.0.0/8` - Another common private network range

**For more security**, you can restrict to specific IP ranges:
```
# More restrictive - only allow Docker Desktop's network
host    all             all             192.168.65.0/24          md5
```

3. Save the file
4. Reload PostgreSQL configuration (no restart needed):
   ```sql
   -- Connect to PostgreSQL and run:
   SELECT pg_reload_conf();
   ```
   
   Or restart the service:
   ```powershell
   Restart-Service postgresql-x64-<version>
   ```

### Step 4: Configure Windows Firewall

1. Open **Windows Defender Firewall** (wf.msc)
2. Click **Inbound Rules** → **New Rule**
3. Select **Port** → **Next**
4. Select **TCP** and enter port **5432** → **Next**
5. Select **Allow the connection** → **Next**
6. Check all profiles (Domain, Private, Public) → **Next**
7. Name it "PostgreSQL Docker Access" → **Finish**

**Or use PowerShell (Run as Administrator):**
```powershell
New-NetFirewallRule -DisplayName "PostgreSQL Docker Access" -Direction Inbound -LocalPort 5432 -Protocol TCP -Action Allow
```

### Step 5: Verify PostgreSQL is Listening

Check if PostgreSQL is listening on all interfaces:

```powershell
# Check listening ports
netstat -an | findstr :5432
```

You should see something like:
```
TCP    0.0.0.0:5432           0.0.0.0:0              LISTENING
```

If you only see `127.0.0.1:5432`, PostgreSQL is still only listening on localhost.

### Step 6: Test Connection from Docker

```bash
# Test connection from Docker container
docker compose exec web python manage.py dbshell

# Or test with psql from container
docker compose exec web sh -c "PGPASSWORD=$DBPASS psql -h host.docker.internal -U $DBUSER -d $DBNAME -c 'SELECT version();'"
```

## Alternative Solutions

### Option 1: Use Host Network Mode (Windows Docker Desktop)

If `host.docker.internal` doesn't work, you can try using the host's IP address directly:

1. Find your Windows host IP address:
   ```powershell
   ipconfig
   # Look for IPv4 Address (usually 192.168.x.x or 10.x.x.x)
   ```

2. Update `docker-compose.yml`:
   ```yaml
   environment:
     - DBHOST=192.168.1.100  # Replace with your actual IP
   ```

### Option 2: Use Gateway IP

Try using Docker's gateway IP instead:

```yaml
environment:
  - DBHOST=172.17.0.1  # Docker's default gateway
```

### Option 3: Port Forwarding

If nothing else works, you can expose PostgreSQL port and connect via localhost:

1. Update `docker-compose.yml` to add port mapping (temporary):
   ```yaml
   # Add this temporarily to test
   ports:
     - "5433:5432"  # Map to different port to avoid conflict
   ```

2. Connect via `localhost:5433` instead

## Troubleshooting

### Check PostgreSQL Logs

PostgreSQL logs are usually in:
- `C:\Program Files\PostgreSQL\<version>\data\log\`
- Or check Windows Event Viewer → Applications → PostgreSQL

### Verify pg_hba.conf Syntax

```powershell
# Test configuration
& "C:\Program Files\PostgreSQL\<version>\bin\pg_ctl.exe" reload -D "C:\Program Files\PostgreSQL\<version>\data"
```

### Test Connection Manually

```powershell
# From Windows PowerShell
$env:PGPASSWORD="your_password"
& "C:\Program Files\PostgreSQL\<version>\bin\psql.exe" -h localhost -U your_user -d your_database
```

### Check Docker Network

```bash
# Inspect Docker network
docker network inspect bridge

# Check if host.docker.internal resolves
docker compose exec web ping host.docker.internal
```

## Security Notes

⚠️ **Important Security Considerations:**

1. **Don't expose PostgreSQL to the internet** - Only allow local network connections
2. **Use strong passwords** - Don't use default or weak passwords
3. **Limit pg_hba.conf** - Only allow necessary IP ranges
4. **Use SSL** - Enable SSL connections for production
5. **Regular updates** - Keep PostgreSQL updated

## Quick Checklist

- [ ] PostgreSQL `postgresql.conf` has `listen_addresses = '*'`
- [ ] PostgreSQL `pg_hba.conf` allows Docker network ranges
- [ ] PostgreSQL service restarted
- [ ] Windows Firewall allows port 5432
- [ ] `netstat` shows PostgreSQL listening on `0.0.0.0:5432`
- [ ] Docker container can ping `host.docker.internal`
- [ ] Connection test successful

## Still Having Issues?

If you're still having connection issues:

1. **Check PostgreSQL version compatibility**
2. **Try connecting with your actual Windows IP address** instead of `host.docker.internal`
3. **Check if PostgreSQL is running as a service** (not just started manually)
4. **Verify your `.env` file** has correct database credentials
5. **Check Docker Desktop settings** - ensure WSL2 integration is properly configured
