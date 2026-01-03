# Docker PostgreSQL Setup

This folder contains the Docker configuration for running PostgreSQL locally for development.

## Features

- PostgreSQL 17.4 with SSL enabled
- Persistent data storage
- Comprehensive logging
- Query statistics tracking (pg_stat_statements)
- Automatic restart on failure

## Initial Setup

### 1. Install Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop) (Windows/Mac)
- OpenSSL (for generating SSL certificates)
  - Windows: Install Git for Windows (includes OpenSSL) or download from [slproweb.com](https://slproweb.com/products/Win32OpenSSL.html)
  - Mac: `brew install openssl`
  - Linux: Usually pre-installed

### 2. Configure Secrets

The default secrets are already created, but you should change them:

```bash
# Edit these files:
secrets/pg_user.txt     # PostgreSQL username (default: postgres)
secrets/pg_pw.txt       # PostgreSQL password (change this!)
```

### 3. Generate SSL Certificates

Run the PowerShell script to generate self-signed certificates:

```powershell
cd docker
.\generate-certs.ps1
```

Or manually with OpenSSL:

```bash
cd certs
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr -subj "/C=US/ST=State/L=City/O=Development/CN=localhost"
openssl x509 -req -days 365 -in server.csr -signkey server.key -out server.crt
rm server.csr
```

### 4. Start PostgreSQL

```bash
cd docker
docker-compose up -d
```

Verify it's running:

```bash
docker-compose ps
docker-compose logs -f postgres
```

### 5. Update Application Environment

Update your `.env.local` in the project root:

```env
# Local Docker PostgreSQL
POSTGRES_URL="postgresql://postgres:postgres_dev_password_change_me@localhost:5432/postgres?sslmode=require"
POSTGRES_PRISMA_URL="postgresql://postgres:postgres_dev_password_change_me@localhost:5432/postgres?sslmode=require&pgbouncer=true"
POSTGRES_URL_NON_POOLING="postgresql://postgres:postgres_dev_password_change_me@localhost:5432/postgres?sslmode=require"
```

Note: Replace `postgres_dev_password_change_me` with the password you set in `secrets/pg_pw.txt`

### 6. Run Database Migrations

From the project root:

```bash
npx prisma migrate dev --name init
```

## Daily Usage

### Start Database

```bash
cd docker
docker-compose up -d
```

### Stop Database

```bash
docker-compose down
```

### View Logs

```bash
# Follow logs
docker-compose logs -f postgres

# View log files directly
cat logs/postgresql.log
```

### Connect to Database

```bash
# Using psql in Docker
docker exec -it postgres psql -U postgres

# Or using a client like pgAdmin, DBeaver, etc.
# Host: localhost
# Port: 5432 (default)
# Database: postgres
# Username: (from secrets/pg_user.txt)
# Password: (from secrets/pg_pw.txt)
# SSL: Required
```

### Reset Database (Delete All Data)

⚠️ **Warning: This will delete all data!**

```bash
docker-compose down
rm -rf data/*
docker-compose up -d
npx prisma migrate dev
```

## Troubleshooting

### "Permission denied" for server.key

PostgreSQL requires the private key to have specific permissions. The Docker container should handle this automatically, but if you have issues:

On Linux/Mac:
```bash
chmod 600 certs/server.key
```

On Windows: The container will set permissions automatically.

### "Connection refused" on localhost:5432

1. Verify container is running: `docker-compose ps`
2. Check logs: `docker-compose logs postgres`
3. Ensure port 5432 is not already in use: `netstat -ano | findstr 5432`
4. Try restarting: `docker-compose restart`

### "SSL connection error"

1. Verify certificates exist in `certs/` folder
2. Regenerate certificates: `.\generate-certs.ps1`
3. Check certificate permissions
4. Restart container: `docker-compose restart`

### "Password authentication failed"

1. Verify password in `secrets/pg_pw.txt` matches your connection string
2. Check username in `secrets/pg_user.txt`
3. Restart container to apply new secrets: `docker-compose down && docker-compose up -d`

## File Structure

```
docker/
├── docker-compose.yml       # Docker Compose configuration
├── generate-certs.ps1       # SSL certificate generation script
├── README.md                # This file
├── .gitignore               # Git ignore rules
├── data/                    # PostgreSQL data files (ignored by git)
├── logs/                    # PostgreSQL logs (ignored by git)
├── certs/                   # SSL certificates (ignored by git)
│   ├── server.crt
│   └── server.key
└── secrets/                 # Database credentials (ignored by git)
    ├── pg_user.txt
    └── pg_pw.txt
```

## Configuration Details

### Network Mode: Host

The container uses `network_mode: "host"` which means it binds directly to localhost:5432. This simplifies local development but is NOT recommended for production.

### Logging

All queries, connections, and disconnections are logged to:
- Console: `docker-compose logs`
- Files: `logs/postgresql.log` and `logs/postgresql.csv`

Logs rotate daily automatically.

### Statistics

Query statistics are tracked via `pg_stat_statements`. To view:

```sql
-- Connect to database
docker exec -it postgres psql -U postgres

-- Enable extension
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- View query statistics
SELECT * FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 10;
```

## Production Notes

For production deployment:

1. Use a managed PostgreSQL service (Vercel Postgres, AWS RDS, etc.)
2. Change from `network_mode: host` to proper networking
3. Use strong passwords and secure secret management
4. Use proper SSL certificates (not self-signed)
5. Configure backup strategies
6. Implement monitoring and alerting

This Docker setup is **for local development only**.
