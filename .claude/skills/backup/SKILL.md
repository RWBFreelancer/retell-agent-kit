---
name: backup
description: Runs retell-clients/tools/backup.ps1 to copy the clients repo to Google Drive, and reports what it copied. Use when asked to back up client data, or on a schedule the client set.
---

# Backup

```powershell
pwsh retell-clients\tools\backup.ps1
```

Report:

- The destination path it copied to.
- The line it wrote to `backup-log.txt`.
- Confirm no `.env`, `.env.local`, or key value went into the copy or
  the log. If the script's own exclude list changed, check this by hand
  before trusting it.

Large media (audio, recordings, PDFs over 50 MB) does not live in git.
Confirm it is under `retell_backups/<client>/media/` instead, not the
repo.
