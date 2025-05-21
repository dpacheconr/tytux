#!/bin/bash
# Simple launcher script for TyTuX

# Check for Python and required environment
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not found"
    exit 1
fi

# Check for .env file
if [ ! -f .env ]; then
    echo "Warning: .env file not found. Creating template..."
    cat > .env << EOF
# Get your Gemini API key from https://aistudio.google.com/apikey
GEMINI_API_KEY=your_gemini_api_key_here
NEW_RELIC_USER_API_KEY=your_new_relic_api_key_here
NEW_RELIC_ACCOUNT_ID=your_account_id_here
NEW_RELIC_API_ENDPOINT=https://api.newrelic.com/graphql
EOF
    echo "Please edit the .env file with your API keys before running again."
    exit 1
fi

# Install requirements if needed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment and installing dependencies..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Run the app
echo "Starting TyTuX..."
python simplechat_app.py
