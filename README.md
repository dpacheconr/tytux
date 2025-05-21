# 🚀 TyTuX - New Relic GraphQL API Assistant

![TyTuX Logo](./logo.jpeg)

TyTuX is an interactive assistant powered by **Gemini AI** that helps you interact with **New Relic's GraphQL API** using natural language. It translates your questions into GraphQL queries and presents the results in a user-friendly way.

## Project Status

✅ **Simplified & Optimized**: We've streamlined the codebase for maximum reliability and maintainability  
✅ **Easy to Run**: Simple launcher script handles setup and execution  
✅ **Stable Implementation**: Direct API integration without complex dependencies  
✅ **User-Friendly Interface**: Clean web UI for interacting with New Relic data  

---

## ✨ Features
- 🤖 **Integrates with Gemini AI** for generating intelligent responses
- 📊 **Queries New Relic data** using natural language
- 💬 **Chat-based interface** for easy interaction
- 🔍 **Schema inspection** to discover available data and queries
- 📱 **Web-based UI** for desktop and mobile use

---

## 📋 Requirements
- 🐍 **Python**: Version 3.9 or higher
- 🔑 A `.env` file with the following environment variables:
  - `GEMINI_API_KEY`: Your `Gemini API key` -> https://aistudio.google.com/apikey
  - `NEW_RELIC_USER_API_KEY`: Your New Relic User API key
  - `NEW_RELIC_ACCOUNT_ID`: Your New Relic account ID
  - `NEW_RELIC_API_ENDPOINT` (optional): Defaults to `https://api.newrelic.com/graphql`

---

## ⚙️ Setup Instructions

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/dpacheconr/tytux
cd tytux
```

### 2️⃣ Create a Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3️⃣ Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4️⃣ Configure Environment Variables
```bash
cp .env-example .env
# Edit .env file with your API keys and account ID
```

### 5️⃣ Run the Application

#### Option 1: Using the launcher script (recommended)
```bash
./run.sh
```
The launcher script will:
- Check for required dependencies
- Create a virtual environment if needed
- Install required packages
- Start the TyTuX web server

#### Option 2: Manual startup
```bash
python3 simplechat_app.py
```

After starting, open your browser to [http://localhost:8000](http://localhost:8000)

---

## 🧩 How It Works

TyTuX uses a streamlined implementation:

### Direct API Implementation (`simplechat.py`)
- Makes direct HTTP requests to New Relic's GraphQL API
- Simple and reliable in all environments
- No external dependencies beyond Python packages
- Optimized for performance and stability

Both implementations use Gemini AI to:
1. Generate GraphQL queries based on your natural language questions
2. Execute the queries against New Relic's API
3. Format and explain the results in a user-friendly way

---

## 🚧 Troubleshooting

### Common Issues

- **Async context errors**: If you encounter errors related to async context management, use the simplified interface with `simplechat_app.py` which avoids these issues
- **API key errors**: Ensure your environment variables are set correctly in the `.env` file
- **GraphQL errors**: Some complex queries may not work correctly; try rephrasing your question or using more specific terms

### Debugging

If you encounter issues:

1. Check the terminal output for error messages
2. Verify API keys are correctly set in your `.env` file
3. Ensure all Python dependencies are installed

---

## 💡 Example Prompts

Here are some example prompts to get started:

1. **Inspect the schema**:
   - _"Show me the NerdGraph API schema"_

2. **Get your account information**:
   - _"Show me my account information"_

3. **List alert policies**:
   - _"List my alert policies"_

4. **Show recent errors**:
   - _"Show me recent errors in my application"_

---

## 📖 Additional Resources
- [New Relic GraphQL API Documentation](https://docs.newrelic.com/docs/apis/nerdgraph/get-started/introduction-new-relic-nerdgraph/)
- [Gemini AI Documentation](https://ai.google.dev/gemini-api/docs)
