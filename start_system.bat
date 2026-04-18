@echo off
echo ========================================
echo   AMATS - AI Multi-Asset Trading System
echo ========================================
echo.

echo [1/3] Refreshing data cache from Mainnet...
python data_cache.py

echo.
echo [2/3] Starting Dashboard (Flask) on port 5000...
start cmd /k "python app.py"

echo [3/4] Starting Live Strategy Engine (Testnet)...
start cmd /k "python strategy_engine.py"

echo.
echo [4/4] Starting Auto-GitHub Sync Backup...
start cmd /k "python auto_push.py"

echo.
echo All systems are now running in separate windows!
echo Dashboard: http://localhost:5000
echo Engine:    strategy_engine.py (Testnet mode)
echo Sync:      auto_push.py (Pushing every 15 min)
echo.
pause
