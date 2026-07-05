# VPS Cron Sync Setup

The VPS auto-pulls the skill from GitHub every 2 hours via a cron job.

## Cron job

Job ID: `e234275c8965`
Schedule: `0 */2 * * *` (every 2 hours)
Delivery: `local` (silent — no Telegram messages)
Script: `sync-skill-marine.sh`

## Sync script on VPS

Located at `~/.hermes/scripts/sync-skill-marine.sh`:

```bash
#!/bin/bash
# Auto-sync marine-procurement-agent skill from GitHub
# Silent when already synced, logs when a new commit is pulled
LOCKFILE="/tmp/marine-skill-sync.lock"
exec 200>"$LOCKFILE"
flock -n 200 || exit 0

REPO_DIR="$HOME/.hermes/skills/maritime/marine-procurement-agent"

# First run / VPS reset: clone fresh
if [ ! -d "$REPO_DIR/.git" ]; then
    if [ -d "$REPO_DIR" ]; then
        mv "$REPO_DIR" "$REPO_DIR.old.$(date +%Y%m%d%H%M%S)"
    fi
    git clone https://github.com/rubinagentagi-tech/marine-procurement-agent.git "$REPO_DIR" 2>&1
    echo "Cloned marine-procurement-agent skill from GitHub"
    exit 0
fi

cd "$REPO_DIR"
git fetch --quiet origin main 2>&1

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

[ "$LOCAL" = "$REMOTE" ] && exit 0

git pull --rebase origin main 2>&1
echo "marine-procurement-agent skill updated: $(git rev-parse --short HEAD)"
```

## How it was created

```bash
# Create the script
cat > ~/.hermes/scripts/sync-skill-marine.sh << 'EOF'
... (script above) ...
EOF
chmod +x ~/.hermes/scripts/sync-skill-marine.sh

# Register cron job
hermes cron create "0 */2 * * *" \
  --name "sync-marine-skill" \
  --script "sync-skill-marine.sh" \
  --no-agent \
  --deliver local
```

## Key design decisions

- **no-agent mode**: The script IS the job — no LLM runs. Just git pull, cheap and fast.
- **Silent when synced**: No Telegram spam every 2 hours. Only logs when a new commit is pulled or on error.
- **Flock**: Prevents concurrent syncs if a previous run is still active.
- **Idempotent**: Safe to run anytime. Clones from scratch if repo dir is missing (VPS reset).
- **local delivery**: Logs go to cron output logs, not to the user's Telegram. The user only sees results from actual procurement requests.
