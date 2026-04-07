@echo off
echo ========================================
echo   AI Trading System - Multi-Asset
echo ========================================
echo.

echo [1/3] Refreshing data cache from Mainnet...
python data_cache.py

echo.
echo [2/3] Starting Dashboard on port 8520...
start cmd /k "streamlit run app.py --server.port 8520"

echo [3/3] Starting Live Strategy Engine...
start cmd /k "python strategy_engine.py"

echo.
echo All systems are now running in separate windows!
echo Dashboard: http://localhost:8520
echo.
pause
