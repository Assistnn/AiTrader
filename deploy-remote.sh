#!/bin/bash
# ===========================================
#  AI Trading System - Remote Deploy Script
#  Usage: ./deploy-remote.sh
#  Runs from: Local Mac → SSH to Xserver VPS
# ===========================================

set -e

VPS_HOST="162.43.56.158"
VPS_USER="Administrator"
VPS_PASS="Etc22070##"
SSH_OPTS="-o PreferredAuthentications=password -o PubkeyAuthentication=no -o StrictHostKeyChecking=no"

ssh_cmd() {
    sshpass -p "$VPS_PASS" ssh $SSH_OPTS ${VPS_USER}@${VPS_HOST} "$1" 2>&1 | grep -v "WARNING" | grep -v "vulnerable" | grep -v "upgraded"
}

echo ""
echo "============================================"
echo " AI Trading System - Remote Deploy"
echo " Target: ${VPS_HOST}"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"
echo ""

# Step 1: Git push (local)
echo "[1/3] Pushing local changes to GitHub..."
cd "$(dirname "$0")"
git push origin main
echo "[OK] Pushed to GitHub."
echo ""

# Step 2: Run deploy.bat on VPS
echo "[2/3] Running deploy.bat on VPS..."
ssh_cmd "cd C:\\ai_trading_system & C:\\ai_trading_system\\deploy.bat"
echo ""

# Step 3: Health check
echo "[3/3] Health check..."
sleep 3

BACKEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://${VPS_HOST}:8000/docs" 2>/dev/null || echo "000")
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://${VPS_HOST}:3000" 2>/dev/null || echo "000")

echo "  Backend  (port 8000): HTTP ${BACKEND_STATUS}"
echo "  Frontend (port 3000): HTTP ${FRONTEND_STATUS}"

if [ "$BACKEND_STATUS" = "200" ] && [ "$FRONTEND_STATUS" = "200" ]; then
    echo ""
    echo "============================================"
    echo " Deploy SUCCESS!"
    echo " Backend:  http://${VPS_HOST}:8000/docs"
    echo " Frontend: http://${VPS_HOST}:3000"
    echo "============================================"
else
    echo ""
    echo "[WARN] Some services may not be responding."
    echo "Check VPS logs: ssh Administrator@${VPS_HOST}"
fi
