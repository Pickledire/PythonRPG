#!/bin/bash
set -e
echo "Starting RPG Game..."

# Ensure we're in the script directory
cd "$(dirname "$0")"

# Detect or install python3
need_py=false
if ! command -v python3 >/dev/null 2>&1; then
  need_py=true
fi

if [ "$need_py" = true ]; then
  echo "Python3 not found. Attempting to install..."
  if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS: install Homebrew if needed, then Python
    if ! command -v brew >/dev/null 2>&1; then
      echo "Homebrew not found. Installing Homebrew (may prompt for password)..."
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
      eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || true
      eval "$(/usr/local/bin/brew shellenv)" 2>/dev/null || true
    fi
    echo "Installing python@3 via Homebrew..."
    brew install python || { echo "Please install Python 3 manually: https://www.python.org/downloads/"; exit 1; }
  else
    # Linux: try apt/yum/dnf
    if command -v apt-get >/dev/null 2>&1; then
      echo "Installing python3 via apt-get (may prompt for password)..."
      sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip || true
    elif command -v dnf >/dev/null 2>&1; then
      echo "Installing python3 via dnf (may prompt for password)..."
      sudo dnf install -y python3 python3-pip || true
    elif command -v yum >/dev/null 2>&1; then
      echo "Installing python3 via yum (may prompt for password)..."
      sudo yum install -y python3 python3-pip || true
    fi
  fi
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: Python 3 is required. Please install it from https://www.python.org/downloads/"
  exit 1
fi

# Create or activate virtual environment
if [ -d ".venv" ]; then
  echo "Activating virtual environment..."
  source .venv/bin/activate
elif [ -d "venv" ]; then
  echo "Activating virtual environment..."
  source venv/bin/activate
else
  echo "Creating virtual environment..."
  python3 -m venv .venv || true
  if [ -d ".venv" ]; then
    source .venv/bin/activate
  fi
fi

# Ensure pip is present and up-to-date
python3 -m ensurepip -q || true
python3 -m pip install --upgrade pip -q || true

# Install dependencies
if [ -f "requirements.txt" ]; then
  echo "Installing dependencies..."
  python3 -m pip install -r requirements.txt || {
    echo "Failed to install dependencies. Try manually: python3 -m pip install -r requirements.txt"; exit 1; }
fi

# Run the game using python3
python3 Main.py

