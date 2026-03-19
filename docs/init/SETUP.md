# Database Setup Guide

Local PostgreSQL + pgvector setup for the Supertroopers hiring platform.

---

## Prerequisites

- Windows 11
- PostgreSQL 15+ installed locally (assumed already installed)
- Admin/superuser access to your PostgreSQL instance

---

## 1. Verify PostgreSQL Installation

Open a terminal and confirm PostgreSQL is running:

```bash
psql --version
pg_isready
```

If `pg_isready` returns "accepting connections" you're good. If not, start the service:

```powershell
# PowerShell (admin)
net start postgresql-x64-17
```

Adjust the service name if your version differs (e.g., `postgresql-x64-16`).

---

## 2. Install pgvector Extension

pgvector does not ship with PostgreSQL by default. You need to install it separately.

### Option A: Pre-built binary (recommended for Windows)

1. Go to https://github.com/pgvector/pgvector/releases
2. Download the Windows release matching your PostgreSQL version (e.g., `pgvector-0.8.0-pg17-windows-x64.zip`)
3. Extract the archive
4. Copy the files to your PostgreSQL installation:
   - `vector.dll` goes to `C:\Program Files\PostgreSQL\17\lib\`
   - `vector.control` and `vector--*.sql` files go to `C:\Program Files\PostgreSQL\17\share\extension\`
5. Restart PostgreSQL

### Option B: Build from source (if binaries aren't available)

Requires Visual Studio Build Tools with C compiler:

```powershell
git clone https://github.com/pgvector/pgvector.git
cd pgvector

# Set PGROOT to your PostgreSQL install
set "PGROOT=C:\Program Files\PostgreSQL\17"

# Build and install
nmake /F Makefile.win
nmake /F Makefile.win install
```

Restart PostgreSQL after installing.

### Verify pgvector is available

```bash
psql -U postgres -c "SELECT * FROM pg_available_extensions WHERE name = 'vector';"
```

You should see `vector` in the output with its version.

---

## 3. Create the Database

Connect as your PostgreSQL superuser and create the database:

```bash
psql -U postgres
```

```sql
CREATE DATABASE supertroopers;
\q
```

---

## 4. Run Migrations

From the project root, run each migration in order against the `supertroopers` database:

```bash
# Migration 001: Schema (tables, indexes, views, triggers)
psql -U postgres -d supertroopers -f code/db/migrations/001_initial_schema.sql

# Migration 002: Seed reference data (skills, summary variant placeholders)
psql -U postgres -d supertroopers -f code/db/migrations/002_seed_enums.sql
```

If you use a different username or need a password:

```bash
psql -U your_username -d supertroopers -W -f code/db/migrations/001_initial_schema.sql
```

Both migrations run inside transactions. If anything fails, the entire migration rolls back cleanly.

---

## 5. Verify the Setup

Connect to the database and run these checks:

```bash
psql -U postgres -d supertroopers
```

```sql
-- Check pgvector is enabled
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';

-- List all tables (should show 10 tables + schema_migrations)
\dt

-- List all views (should show 3 views)
\dv

-- Check migration history
SELECT * FROM schema_migrations ORDER BY version;

-- Verify seed data loaded
SELECT COUNT(*) AS skill_count FROM skills;
SELECT role_type FROM summary_variants ORDER BY role_type;

-- Test vector operations work
SELECT '[1,2,3]'::vector;
```

### Expected output

| Check | Expected |
|-------|----------|
| Tables | career_history, bullets, skills, summary_variants, companies, applications, interviews, contacts, emails, documents, resume_versions, schema_migrations |
| Views | application_funnel, source_effectiveness, monthly_activity |
| Migrations | 001 (initial_schema), 002 (seed_enums) |
| Skills count | 40 |
| Summary variants | 7 role types |

---

## Connection Details (for application config)

| Setting | Value |
|---------|-------|
| Host | localhost |
| Port | 5432 |
| Database | supertroopers |
| Username | postgres (or your user) |
| Password | (your local password) |

Connection string format:

```
postgresql://postgres:YOUR_PASSWORD@localhost:5432/supertroopers
```

---

## Troubleshooting

### "extension vector does not exist"
pgvector isn't installed or PostgreSQL hasn't been restarted after installing it. Re-check step 2.

### "permission denied"
You need superuser privileges to create extensions. Connect as `postgres` or grant your user the `SUPERUSER` role.

### "database supertroopers already exists"
That's fine... just skip step 3 and run the migrations.

### Migration fails partway through
Migrations are transactional. If one fails, nothing was committed. Fix the issue and re-run the migration.

### HNSW index creation is slow
The HNSW indexes are created on empty tables, so they should be instant. If you add data first and then create indexes, it will take longer. The migration creates indexes before data load intentionally.
