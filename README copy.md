# TyTuX - Command Your Data

![TyTuX Logo](./logo.jpeg)

TyTuX is an interactive assistant powered by MCP and Gemini AI.
It allows users to interact with New Relic Graphql API through a conversational interface.

---

## Features
- Connects to MCP servers using `npx`.
- Integrates with Gemini AI for generating responses.
- Supports tool invocation and interaction during conversations.
- Maintains conversation history for context-aware responses.

---

## Requirements
- Python 3.12 or higher
- Node.js (with `npx` installed)
- A `.env` file with the following environment variables:
  - `GEMINI_API_KEY`: Your Gemini API key.
  - `NEW_RELIC_USER_API_KEY`: Your New Relic User API key.
  - `NEW_RELIC_API_ENDPOINT` (optional): Defaults to `https://api.newrelic.com/graphql`.
  - `ALLOW_MUTATIONS` (optional): Defaults to `false`.

---

## Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/dpacheconr/tytux
cd tytux

# Create the virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

# Create .env for credentials 
cp .env-example .env

# Run script
python3 client.py
```

## Example prompts

- First we ask Gemini to use our account id for ongoing queries and to also inspect the nerdgraph api schema when we don't provide the query to run in the prompt 
  - going forward for each prompt, always inspect schema when nrql query is not provided and use account id YOUR_ACCOUNT_ID_HERE
- Then let's get all the alerts on our account and ask for some suggestions how to improve them 
  - get all alerts using nrqlconditionssearch, include total count,nrqlcondition nrql query and id in the results, then suggest possible improvements, like adding where clauses to each nrql where appropriate