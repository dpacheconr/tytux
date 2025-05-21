#!/bin/bash
# run_tytux.sh - Script to run the fixed TyTuX application

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not installed. Please install Python 3 first."
    exit 1
fi

# Check if npx is installed
if ! command -v npx &> /dev/null; then
    echo "npx (Node.js) is required but not installed. Please install Node.js first."
    exit 1
fi

echo "======================================="
echo "TyTuX - Command Your Data"
echo "======================================="

# Check for .env file
if [ ! -f .env ]; then
    echo "WARNING: .env file not found. Please create one with the required environment variables:"
    echo "- GEMINI_API_KEY"
    echo "- NEW_RELIC_USER_API_KEY"
    echo "- NEW_RELIC_ACCOUNT_ID"
fi

# Check for required packages
echo "Checking for required Python packages..."
REQUIRED_PACKAGES=("flask" "google-generativeai" "python-dotenv" "mcp-client")
MISSING_PACKAGES=()

for package in "${REQUIRED_PACKAGES[@]}"; do
    if ! python3 -c "import $package" 2>/dev/null; then
        MISSING_PACKAGES+=("$package")
    fi
done

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo "Some required packages are missing. Installing them now..."
    python3 -m pip install ${MISSING_PACKAGES[@]}
fi

# Run the fixed Flask application
echo ""
echo "Starting the TyTuX Flask web interface..."
echo "Press Ctrl+C to stop the server."
echo ""
python3 webapp_fixed.py
