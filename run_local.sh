#!/bin/bash

# Configuration
VENV_DIR="venv"
REQUIREMENTS_FILE="requirements.txt"
APP_ENTRY_POINT="app.main:app"
PORT=8000

echo "🚀 Setting up TenderScout UK for local run..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not installed or not in PATH."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv $VENV_DIR
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source $VENV_DIR/bin/activate

# Install requirements
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r $REQUIREMENTS_FILE

# Create data directory if it doesn't exist
mkdir -p data

# Ensure .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️ Warning: .env file not found. Creating a template..."
    echo "TELEGRAM_BOT_TOKEN=" > .env
    echo "TELEGRAM_CHAT_ID=" >> .env
    echo "Please fill in the .env file with your credentials."
fi

# Run the application
echo "🌟 Starting the application..."
uvicorn $APP_ENTRY_POINT --reload --host 0.0.0.0 --port $PORT

