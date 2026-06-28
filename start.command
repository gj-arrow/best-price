#!/bin/bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
ENV_FILE="$ROOT_DIR/.env"
PID_FILE="/tmp/price-compare.pids"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cleanup() {
    echo -e "\n${YELLOW}Shutting down...${NC}"
    if [ -f "$PID_FILE" ]; then
        while IFS= read -r pid; do
            kill "$pid" 2>/dev/null || true
        done < "$PID_FILE"
        rm -f "$PID_FILE"
    fi
    wait
    echo -e "${GREEN}Done.${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# --- PostgreSQL ---
echo -e "${YELLOW}[1/3] Checking PostgreSQL...${NC}"
if brew services list | grep -q "postgresql@15.*started"; then
    echo -e "${GREEN}  PostgreSQL already running.${NC}"
elif brew services list | grep -q "postgresql@15.*none"; then
    echo -e "${YELLOW}  Starting PostgreSQL...${NC}"
    brew services run postgresql@15 &
    sleep 2
else
    echo -e "${YELLOW}  Starting PostgreSQL...${NC}"
    brew services start postgresql@15
    sleep 2
fi

# --- Fix DATABASE_URL for local dev (replace @db: with @localhost:) ---
if grep -q "@db:" "$ENV_FILE" 2>/dev/null; then
    echo -e "${YELLOW}  Fixing DATABASE_URL for local dev (db -> localhost)...${NC}"
    sed -i '' 's/@db:/@localhost:/g' "$ENV_FILE"
fi

# --- Backend ---
echo -e "${YELLOW}[2/3] Starting backend (uvicorn)...${NC}"
cd "$BACKEND_DIR"
SSL_CERT_FILE=$(python3 -m certifi) uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$PID_FILE"

# Wait for backend
for i in $(seq 1 30); do
    if curl -s "http://localhost:8000/health" > /dev/null 2>&1; then
        echo -e "${GREEN}  Backend ready on http://localhost:8000${NC}"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo -e "${RED}  Backend failed to start${NC}"
        cleanup
    fi
    sleep 1
done

# --- Frontend ---
echo -e "${YELLOW}[3/3] Starting frontend (Next.js)...${NC}"
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!
echo "$FRONTEND_PID" >> "$PID_FILE"

echo ""
echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}  Site is starting up!${NC}"
echo -e "${GREEN}  Frontend: http://localhost:3000${NC}"
echo -e "${GREEN}  Backend:  http://localhost:8000${NC}"
echo -e "${GREEN}  API docs: http://localhost:8000/docs${NC}"
echo -e "${GREEN}====================================${NC}"
echo -e "${YELLOW}  Press Ctrl+C to stop all services${NC}"
echo ""

# Open browser
open http://localhost:3000

wait
