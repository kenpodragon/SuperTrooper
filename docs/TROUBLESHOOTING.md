# SuperTroopers Troubleshooting Guide

Platform: Windows 11 (primary). Mac untested — see Section 8.

Services and ports:
- PostgreSQL: port 5555 (container: supertroopers-db)
- Flask API: port 8055 (container: supertroopers-app)
- MCP SSE server: port 8056 (container: supertroopers-app)
- React frontend: port 5175 (container: supertroopers-web)

---

## 1. Docker Issues

### Docker Desktop won't start

**Symptom:** Docker Desktop fails to launch, shows WSL2 error, or freezes on startup.

**Cause A — WSL2 not enabled:**
Docker Desktop on Windows requires WSL2. If it wasn't enabled before install, Docker can't start.

Fix: Enable WSL2 via PowerShell (run as Administrator):
```powershell
wsl --install
wsl --set-default-version 2
```
Then restart your PC. Full instructions: https://learn.microsoft.com/en-us/windows/wsl/install

**Cause B — Hyper-V conflict with other VMs:**
VMware Workstation and VirtualBox (pre-7.0) conflict with Hyper-V, which Docker needs.

Fix: Either upgrade VirtualBox to 7.0+ (supports Hyper-V coexistence), or switch VMware to use the Windows Hypervisor Platform. Check Docker Desktop documentation for your VM software version.

---

### `docker compose up` fails with port conflict

**Symptom:** Error like `Bind for 0.0.0.0:5555 failed: port is already allocated`.

**Cause:** Another process is using one of the required ports (5555, 8055, 8056, 5175).

Fix — find what's using the port (PowerShell or CMD):
```powershell
netstat -ano | findstr :5555
```
Note the PID in the last column, then kill it:
```powershell
taskkill /PID <PID> /F
```
Repeat for any conflicting port, then retry `docker compose up -d`.

---

### Container exits immediately after starting

**Symptom:** `docker ps` shows supertroopers-app is not running or shows "Exited".

**Cause:** Usually a missing or misconfigured `.env` file, most often `DB_PASSWORD` not set.

Fix:
```bash
docker logs supertroopers-app
```
Look for `KeyError`, `missing environment variable`, or connection refused errors. Then:
1. Verify `code/backend/.env` exists
2. Verify it contains `DB_PASSWORD=WUHD8fBisb57FS4Q3bdvfuvgnim9fL1c` (or your configured password)
3. Restart: `cd code && docker compose up -d`

---

### DB container unhealthy

**Symptom:** `docker ps` shows supertroopers-db as `(unhealthy)`.

**Cause A — Disk space:** PostgreSQL can't write WAL or data files.
Check: `docker system df` to see Docker disk usage. Free up space or prune unused images: `docker system prune`.

**Cause B — Permissions on db_data bind mount:**
The `db_data` folder must be writable by the Docker process.
Fix: Right-click the `code/db_data` folder in Explorer, Properties > Security, give your user full control. Or run Docker Desktop as Administrator.

**Cause C — Corrupted data directory:**
If the container was killed mid-write, the data directory may be corrupted.
Fix (destructive — deletes all DB data):
```bash
cd code
docker compose down
rm -rf db_data
docker compose up -d
```
Then re-run migrations and re-import your data.

---

### Containers start but API doesn't respond

**Symptom:** All containers show as running, but `http://localhost:8055/api/health` times out or refuses connection.

**Cause:** The app container is waiting for PostgreSQL to be ready. The health check has a grace period.

Fix: Wait 15-30 seconds after `docker compose up -d`, then retry. If it still doesn't respond after a minute:
```bash
docker logs supertroopers-app
```
Look for DB connection errors. If the DB is slow to initialize (first run), the app may have given up — restart it:
```bash
docker compose restart supertroopers-app
```

---

## 2. API Issues

### Health endpoint returns error

**Symptom:** `curl http://localhost:8055/api/health` returns an error or `{"status": "error"}`.

**Cause:** DB_PASSWORD in `.env` doesn't match the password the database was initialized with.

Fix:
1. Check `code/backend/.env` for `DB_PASSWORD`
2. That value must match what was used when the `db_data` directory was first created
3. If you changed the password after first run, either revert it or wipe `db_data` and reinitialize

---

### 404 on API endpoints

**Symptom:** API calls return 404 for routes you know exist.

**Cause:** You changed backend code but the container is still running the old image.

Fix — rebuild and restart:
```bash
cd code && docker compose up -d --build
```

---

### CORS errors from frontend

**Symptom:** Browser console shows `Access-Control-Allow-Origin` errors when the frontend calls the API.

**Cause A — Vite proxy misconfiguration:**
The React dev server (port 5175) should proxy `/api` requests to port 8055. Check `code/frontend/vite.config.ts` and verify the proxy target is `http://localhost:8055`.

**Cause B — Direct API call from wrong origin:**
Fix: Confirm you're accessing the app at `http://localhost:5175`, not via an IP address or different hostname. CORS is configured for localhost.

**Workaround — test the API directly:**
```bash
curl http://localhost:8055/api/health
```
If this works, the API is fine and the issue is in the frontend proxy config.

---

## 3. MCP Connection Issues

### Claude Code doesn't see SuperTroopers tools

**Symptom:** SuperTroopers MCP tools don't appear in Claude Code, or tool calls fail with "unknown tool".

**Fix — check these in order:**

1. Verify `.mcp.json` exists in the project root (`c:/Users/ssala/OneDrive/Desktop/Resumes/.mcp.json`)
2. Verify the SSE endpoint URL in `.mcp.json` points to `http://localhost:8056/sse`
3. Verify Docker containers are running: `docker ps --filter "name=supertroopers"`
4. Restart your Claude Code session (close and reopen the terminal/app)
5. Test the SSE endpoint directly:
   ```bash
   curl http://localhost:8056/sse
   ```
   You should see an SSE stream open. If connection refused, the app container isn't running.

For full MCP connection setup, see `code/docs/MCP_REFERENCE.md`.

---

### MCP tool returns connection error

**Symptom:** A SuperTroopers tool call fails with a connection or timeout error mid-session.

**Cause:** Docker containers stopped (Docker Desktop restart, sleep/wake cycle, etc.).

Fix:
```bash
docker ps --filter "name=supertroopers" --format "{{.Names}} {{.Status}}"
cd code && docker compose up -d
```
Wait ~15 seconds, then retry the tool call.

---

### SSE connection drops

**Symptom:** MCP tools work at first, then stop responding or return connection errors.

**Cause:** The app container restarted (OOM kill, Docker Desktop resource limits hit).

Fix:
```bash
docker logs supertroopers-app --tail 50
```
Look for OOM errors or crash messages. If Docker Desktop is killing containers for memory:
- Docker Desktop > Settings > Resources > Memory — increase to at least 4 GB

Then restart:
```bash
cd code && docker compose up -d
```

---

### "Using a different AI agent?" message

See `code/docs/MCP_REFERENCE.md` for the full connection reference and how Claude Code connects to SuperTroopers.

---

## 4. Upload / Parsing Issues

### Upload fails with 400

**Symptom:** File upload returns HTTP 400.

**Cause:** Wrong form field name or unsupported file type.

Fix:
- The multipart form field must be named `files` (plural)
- Only `.docx` and `.pdf` files are accepted
- Check the file extension is lowercase

---

### Parser returns low confidence score

**Symptom:** After upload, the parsed resume has a low confidence score and missing sections.

**Cause:** Complex or non-standard resume formatting confuses the rule-based parser.

Fix: Enable AI-enhanced parsing in Settings. This uses the LLM fallback for sections the rule-based parser couldn't extract confidently.

---

### Template creation fails

**Symptom:** "Could not detect slots automatically" or template creation errors out.

**Cause:** The uploaded .docx is too short, or uses unusual formatting that doesn't match expected section patterns.

Fix: Ensure the source document has at least the standard sections (Summary, Experience, Education, Skills). If formatting is highly customized, manually define slot locations after upload.

---

### Duplicate data after re-upload

**Symptom:** Re-uploading a resume creates duplicate bullets or entries.

**Cause:** Expected behavior — the system deduplicates by similarity threshold, not exact match.

Fix: The dedup threshold is configurable in Settings. Lower the threshold to catch more near-duplicates. For a clean reimport, delete the existing parsed data for that resume before re-uploading.

---

## 5. Resume Generation Issues

### Generated resume has missing content

**Symptom:** Output document is missing sections or bullets that should be there.

**Cause:** The recipe references data rows that were deleted after the recipe was created.

Fix: Run the recipe validate endpoint to identify broken references:
```bash
curl http://localhost:8055/api/recipes/<recipe_id>/validate
```
The response lists any slots pointing to missing rows. Update or remove those slots.

---

### Formatting looks wrong in output document

**Symptom:** Generated .docx has broken formatting, wrong fonts, or misaligned sections.

**Cause:** The template .docx is corrupted or was modified outside the platform.

Fix: Re-upload the original .docx template from `Originals/`. Never edit the template file directly — always go through the platform.

---

### Recipe validation fails

**Symptom:** Recipe validation endpoint returns errors about missing rows.

**Cause:** Slots in the recipe JSON reference database row IDs that no longer exist (deleted or re-imported with new IDs).

Fix: Open the recipe in the platform editor, remove or reassign the broken slots, and re-save.

---

## 6. Frontend Issues

### Page won't load at localhost:5175

**Symptom:** Browser shows "site can't be reached" or connection refused at `http://localhost:5175`.

**Fix — check in order:**
1. Verify the web container is running: `docker ps --filter "name=supertroopers-web"`
2. Check for port conflict: `netstat -ano | findstr :5175`
3. Check container logs: `docker logs supertroopers-web`
4. Restart: `cd code && docker compose restart supertroopers-web`

---

### Data not showing in dashboard

**Symptom:** Frontend loads but tables and charts are empty.

**Cause:** Frontend can't reach the backend API.

Fix:
1. Open browser DevTools > Console — look for network errors
2. Check the API directly: `curl http://localhost:8055/api/health`
3. If the API is down, restart backend: `cd code && docker compose restart supertroopers-app`

---

### Settings not saving

**Symptom:** Changes in the Settings page don't persist after save.

**Cause:** The save request is failing silently.

Fix:
1. Open browser DevTools > Network tab
2. Click Save in Settings — find the failing request
3. Check the response body for the error message
4. Verify the backend container is running and healthy

---

## 7. Windows-Specific Issues

### Path issues with backslashes

**Symptom:** Commands fail with "no such file" errors when paths contain backslashes.

Fix: Use forward slashes in all terminal commands:
```bash
# Wrong
cd c:\Users\ssala\OneDrive\Desktop\Resumes\code

# Correct
cd c:/Users/ssala/OneDrive/Desktop/Resumes/code
```
Or wrap paths in quotes if they contain spaces.

---

### Line ending issues (CRLF vs LF)

**Symptom:** Scripts fail inside Docker containers with "bad interpreter" or syntax errors, even though they look fine.

**Cause:** Windows git converting LF to CRLF on checkout.

Fix:
```bash
git config core.autocrlf true
```
Then re-checkout affected files: `git checkout -- <file>`.

---

### WSL2 consuming too much memory

**Symptom:** PC slows down significantly while Docker is running.

Fix: Docker Desktop > Settings > Resources > Memory — set a cap. Recommended minimum for SuperTroopers: 4 GB. If you have 16 GB RAM, 6-8 GB is a comfortable cap.

---

### "Permission denied" on db_data folder

**Symptom:** DB container fails to start with permission errors on the data directory.

**Fix — option A (preferred):**
Run Docker Desktop as Administrator (right-click > Run as administrator).

**Fix — option B:**
Fix folder permissions manually:
1. Navigate to `code/db_data` in Explorer
2. Right-click > Properties > Security
3. Add your Windows user with Full Control
4. Apply and retry `docker compose up -d`

---

## 8. Mac Users

SuperTroopers was developed and tested on Windows 11 only. Docker Desktop for Mac should work for the core services, but some differences apply:

- **Networking:** On Mac, use `host.docker.internal` instead of `localhost` when referencing the host from inside containers. The `docker-compose.yml` may need adjustment.
- **PDF conversion:** The `docx_to_pdf` script uses Word COM automation on Windows (requires Microsoft Word). On Mac, install LibreOffice and update the script to call LibreOffice's headless conversion: `soffice --headless --convert-to pdf <file>`.
- **Port availability:** Same ports apply (5555, 8055, 8056, 5175). Check for conflicts with `lsof -i :<port>`.

If you encounter Mac-specific issues, please report them on GitHub with:
- Your macOS version
- Your Docker Desktop version
- The exact error message and `docker logs` output

---

## 9. Getting Help

**Quick diagnostics — run these first:**

Check what's running:
```bash
docker ps --filter "name=supertroopers" --format "{{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Check app logs (last 50 lines):
```bash
docker logs supertroopers-app --tail 50
```

Check DB logs:
```bash
docker logs supertroopers-db --tail 50
```

Check API health:
```bash
curl http://localhost:8055/api/health
```

Check MCP SSE endpoint:
```bash
curl http://localhost:8056/sse
```
(Should open an SSE stream — press Ctrl+C to close.)

**If nothing above resolves the issue:**
- Open a GitHub issue with the output of the diagnostics above
- Include your Windows version (`winver`) and Docker Desktop version (Docker Desktop > About)
