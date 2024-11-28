@echo off
echo Starting Mafia Bot...

:: Set environment variables
set BOT_TOKEN=7942602768:AAFORbxBV2pmWaA0UjqmYFN4BWRu4_hQur0
set DB_NAME=mafia_bot
set DB_USER=postgres
set DB_PASSWORD=password123
set DB_HOST=localhost
set DB_PORT=5432

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not found! Please install Python 3.8 or higher.
    pause
    exit /b 1
)

:: Try to run the bot
echo Running the bot...
python run.py
if errorlevel 1 (
    echo Failed to start the bot. Please check if all requirements are installed.
    echo Installing requirements...
    pip install -r requirements.txt
    echo Retrying to start the bot...
    python run.py
)

pause
