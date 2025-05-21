# TyTuX Quick Start Guide

TyTuX is a simple chat interface that connects Google's Gemini AI with New Relic's GraphQL API, allowing you to query your New Relic data using natural language.

## Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Create a `.env` file** with your API keys:
   ```
   GEMINI_API_KEY=your_gemini_api_key_here
   NEW_RELIC_USER_API_KEY=your_new_relic_api_key_here
   NEW_RELIC_ACCOUNT_ID=your_account_id_here
   NEW_RELIC_API_ENDPOINT=https://api.newrelic.com/graphql
   ```
   
   You can get a Gemini API key from: https://aistudio.google.com/apikey

## Running TyTuX

Start the web server:

```bash
python simplechat_app.py
```

Then visit http://localhost:8000 in your browser.

## Usage Tips

1. Start by asking about your account information to verify connectivity
2. Use the "Inspect Schema" button to learn about available data
3. Ask questions in plain English about your New Relic data
4. For best results, be specific in your questions

## Example Queries

- "Show me my account information"
- "List my alert policies"
- "Show recent errors in my application"
- "What are my APM services?"

## Troubleshooting

- Check that your API keys are correctly set in the .env file
- Look at the terminal output for any error messages
- Make sure you have internet connectivity for both New Relic and Gemini API access