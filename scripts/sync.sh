#!/bin/bash
# Marine Procurement Agent — Git Sync Script
# ============================================
# Syncs the skill between laptop, VPS, and GitHub.
# Run AFTER making changes on either machine.
#
# Flow:
#   laptop changes → git push → VPS pulls
#   VPS changes (via Telegram session) → VPS commits + pushes → laptop pulls
#
# Usage: bash sync.sh

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOCKFILE="/tmp/marine-procurement-sync.lock"
BRANCH="main"

exec 200>"$LOCKFILE"
flock -n 200 || { echo "Sync already in progress. Skipping."; exit 0; }

cd "$REPO_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Syncing marine-procurement-agent..."

git fetch --quiet origin "$BRANCH" 2>&1

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH")

if [ "$LOCAL" = "$REMOTE" ]; then
    echo "  Already in sync with origin/$BRANCH ($(echo $LOCAL | cut -c1-7))"
    exit 0
fi

echo "  Pulling changes from origin..."
git pull --rebase origin "$BRANCH" 2>&1
echo "  Pulled — now at $(git rev-parse --short HEAD)"

# Check for local changes
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "  Local changes detected — committing and pushing..."
    git add -A .
    HOSTNAME_SHORT=$(hostname -s 2>/dev/null || echo "unknown")
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S %Z')
    git commit -m "Auto-sync from $HOSTNAME_SHORT at $TIMESTAMP" 2>&1
    git push origin "$BRANCH" 2>&1
    echo "  Pushed new commit: $(git rev-parse --short HEAD)"
fi

echo "  Sync complete."
