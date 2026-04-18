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

echo [3/3] Starting Live Strategy Engine (Testnet)...
start cmd /k "python strategy_engine.py"

echo.
echo All systems are now running in separate windows!
echo Dashboard: http://localhost:5000
echo Engine:    strategy_engine.py (Testnet mode)
echo.
pause
