#!/bin/bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="/tmp/price-compare.pids"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}Stopping price comparison services...${NC}"

# Try PID file first
if [ -f "$PID_FILE" ]; then
    echo -e "${YELLOW}  Using PID file...${NC}"
    while IFS= read -r pid; do
        if kill "$pid" 2>/dev/null; then
            echo -e "${GREEN}  Stopped PID $pid${NC}"
        else
            echo -e "${RED}  PID $pid not found (already stopped)${NC}"
        fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
else
    echo -e "${YELLOW}  No PID file found, searching processes...${NC}"
fi

# Kill remaining processes by name
BACKEND_KILLED=false
FRONTEND_KILLED=false

if pkill -f "uvicorn main:app" 2>/dev/null; then
    echo -e "${GREEN}  Backend (uvicorn) stopped${NC}"
    BACKEND_KILLED=true
fi

if pkill -f "next dev" 2>/dev/null; then
    echo -e "${GREEN}  Frontend (Next.js) stopped${NC}"
    FRONTEND_KILLED=true
fi

if [ "$BACKEND_KILLED" = false ] && [ "$FRONTEND_KILLED" = false ]; then
    if [ ! -f "$PID_FILE" ]; then
        echo -e "${RED}  No running services found.${NC}"
    fi
else
    echo -e "${GREEN}Done.${NC}"
fi
