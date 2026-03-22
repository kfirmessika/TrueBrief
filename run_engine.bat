@echo off
TITLE TrueBrief Delta Engine | Autonomous Mode
ECHO ===================================================
ECHO    TRUEBRIEF INTELLIGENCE SYSTEM | ONLINE
ECHO ===================================================
ECHO.
ECHO [STATUS] Waking up Scheduler...
ECHO [STATUS] Press CTRL+C to stop the engine.
ECHO.
cd src
python -m truebrief.scheduler
PAUSE
