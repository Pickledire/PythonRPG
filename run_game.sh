#!/bin/bash
echo "Starting RPG Game..."

# Check if virtual environment exists and activate it
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Install dependencies (no-op if already installed)
if command -v python3 >/dev/null 2>&1; then
  if [ -f "requirements.txt" ]; then
    python3 -m pip install --user -r requirements.txt >/dev/null 2>&1
  fi
fi

# Run the game using python3
python3 Main.py

