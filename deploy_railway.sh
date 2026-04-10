#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if [ -f ".env" ]; then
  set -a
  source ".env"
  set +a
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "npm / npx wird benötigt. Bitte installiere Node.js/npm."
  exit 1
fi

RAILWAY_CMD="npx @railway/cli"

if ! $RAILWAY_CMD whoami >/dev/null 2>&1; then
  echo "Bitte melde dich bei Railway an..."
  $RAILWAY_CMD login
fi

PROJECT_NAME=${PROJECT_NAME:-namozbot}

if ! $RAILWAY_CMD status >/dev/null 2>&1; then
  echo "Erstelle neues Railway-Projekt: $PROJECT_NAME"
  $RAILWAY_CMD init --name "$PROJECT_NAME" --json
else
  echo "Verzeichnisse sind bereits mit einem Railway-Projekt verbunden."
fi

if [ -z "$BOT_TOKEN" ]; then
  echo "Bitte setze BOT_TOKEN in .env oder als Umgebungsvariable."
  exit 1
fi

echo "Setze Railway-Umgebungsvariable BOT_TOKEN..."
$RAILWAY_CMD variable set BOT_TOKEN="$BOT_TOKEN"

echo "Deploying to Railway..."
$RAILWAY_CMD up --detach

echo "Railway deployment gestartet."
