import os
import json
import asyncio
import signal
import functools
import time
from flask import Flask, request, render_template, jsonify
from client_clean import MCPGeminiAgent

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Create a directory for Flask templates if it doesn't exist
os.makedirs("templates", exist_ok=True)

# Global variables
agent = None
connected = False

class TimeoutError(Exception):
    """Raised when a function times out."""
    pass

def timeout_handler(signum, frame):
    """Handler for timeout signal."""
    raise TimeoutError("Operation timed out")

def run_async(coro, timeout_seconds=30):
    """Run an async function from synchronous Flask code with timeout
    
    Args:
        coro: Coroutine to run
        timeout_seconds: Maximum time to wait before timing out
        
    Returns:
        Result of the coroutine or raises TimeoutError
    """
    loop = asyncio.new_event_loop()
    
    # Set up the timeout handler
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_seconds)
    
    try:
        result = loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout_seconds))
        # Clear the alarm
        signal.alarm(0)
        return result
    except (asyncio.TimeoutError, TimeoutError) as e:
        print(f"Operation timed out after {timeout_seconds} seconds")
        raise TimeoutError(f"Operation timed out after {timeout_seconds} seconds")
    finally:
        loop.close()

@app.route('/')
def index():
    return render_template('index.html', 
                          account_id=os.getenv("NEW_RELIC_ACCOUNT_ID", "Not configured"))

@app.route('/connect', methods=['POST'])
def connect():
    global agent, connected
    
    if agent is None:
        agent = MCPGeminiAgent()
    
    if not connected:
        try:
            # Set a shorter timeout for connection - 15 seconds
            run_async(agent.connect(), timeout_seconds=15)
            connected = True
            return jsonify({"status": "success", "message": "Connected to New Relic GraphQL"})
        except TimeoutError as e:
            return jsonify({
                "status": "error", 
                "message": "Connection timed out. The server may be unresponsive or blocked."
            })
        except Exception as e:
            return jsonify({"status": "error", "message": f"Connection error: {str(e)}"})
    else:
        return jsonify({"status": "success", "message": "Already connected"})

@app.route('/reset_agent', methods=['POST'])
def reset_agent():
    """Reset the agent if it gets into a bad state"""
    global agent, connected
    
    # Close existing agent if it exists
    if agent:
        try:
            run_async(agent.cleanup(), timeout_seconds=5)
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")
    
    # Create a fresh agent
    agent = MCPGeminiAgent()
    connected = False
    
    return jsonify({"status": "success", "message": "Agent has been reset"})

@app.route('/chat', methods=['POST'])
def chat():
    global agent, connected
    
    data = request.json
    message = data.get('message', '').strip()
    
    if not message:
        return jsonify({"status": "error", "message": "Message cannot be empty"})
    
    if agent is None:
        agent = MCPGeminiAgent()
    
    if not connected:
        try:
            run_async(agent.connect(), timeout_seconds=15)
            connected = True
        except TimeoutError as e:
            return jsonify({
                "status": "error", 
                "message": "Connection timed out. Please try resetting the agent."
            })
        except Exception as e:
            return jsonify({"status": "error", "message": f"Connection error: {str(e)}"})
    
    try:
        # Process the message and get the response with a timeout
        start_time = time.time()
        response = run_async(agent.agent_loop(message), timeout_seconds=60)
        end_time = time.time()
        
        print(f"Request processed in {end_time - start_time:.2f} seconds")
        
        # Extract the response text
        if response is None:
            response_text = "No response received. Please try again."
        elif hasattr(response, 'text'):
            response_text = response.text
        elif hasattr(response, 'candidates') and response.candidates:
            response_text = response.candidates[0].content.text
        else:
            response_text = str(response)
            
        return jsonify({
            "status": "success", 
            "response": response_text
        })
    except TimeoutError as e:
        return jsonify({
            "status": "error", 
            "message": "Request timed out. The operation might be too complex or the server is unresponsive. Please try a simpler query or reset the agent."
        })
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": f"Error processing message: {str(e)}"
        })

@app.route('/check_env')
def check_env():
    """Check if environment variables are properly set"""
    required_vars = ["GEMINI_API_KEY", "NEW_RELIC_USER_API_KEY", "NEW_RELIC_ACCOUNT_ID"]
    results = {}
    
    for var in required_vars:
        value = os.getenv(var)
        results[var] = {
            "set": value is not None,
            "length": len(value) if value else 0,
            "preview": value[:3] + "..." if value else None
        }
    
    return jsonify({"status": "success", "results": results})

if __name__ == '__main__':
    print("Creating Flask templates...")
    with open('templates/index.html', 'w') as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
    <title>TyTuX - Command Your Data</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        :root {
            --bg-color: #1e1e1e;
            --text-color: #ffffff;
            --primary-color: #00b5d1;
            --secondary-color: #00c7b1;
            --accent-color: #333333;
            --border-color: #444444;
        }
        
        body {
            font-family: 'Arial', sans-serif;
            margin: 0;
            padding: 0;
            background-color: var(--bg-color);
            color: var(--text-color);
        }
        
        .container {
            max-width: 900px;
            margin: 0 auto;
            padding: 1rem;
        }
        
        header {
            display: flex;
            align-items: center;
            padding: 1rem 0;
        }
        
        .logo {
            width: 60px;
            height: 60px;
            margin-right: 1rem;
        }
        
        h1 {
            margin: 0;
            color: var(--text-color);
        }
        
        .caption {
            color: #bbbbbb;
            margin-top: 0.5rem;
            font-size: 0.9rem;
        }
        
        .chat-container {
            background-color: #2d2d2d;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
            padding: 1.5rem;
            margin-top: 1rem;
            height: calc(100vh - 220px);
            display: flex;
            flex-direction: column;
        }
        
        .chat-messages {
            flex-grow: 1;
            overflow-y: auto;
            margin-bottom: 1rem;
        }
        
        .message {
            margin-bottom: 1rem;
            padding: 1rem;
            border-radius: 18px;
        }
        
        .user-message {
            background: var(--primary-color);
            color: white;
            border-radius: 18px 18px 4px 18px;
            align-self: flex-end;
            margin-left: 20%;
            text-align: right;
        }
        
        .bot-message {
            background: var(--accent-color);
            color: white;
            border-radius: 18px 18px 18px 4px;
            border-left: 4px solid var(--secondary-color);
            align-self: flex-start;
            margin-right: 20%;
        }
        
        .input-container {
            background: var(--accent-color);
            padding: 1rem;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
            border: 1px solid var(--border-color);
        }
        
        .input-row {
            display: flex;
            gap: 10px;
        }
        
        input[type="text"] {
            flex-grow: 1;
            padding: 0.75rem;
            border-radius: 8px;
            border: 2px solid var(--border-color);
            background-color: #333333;
            color: white;
            font-size: 16px;
        }
        
        input[type="text"]:focus {
            border: 2px solid var(--secondary-color);
            outline: none;
            box-shadow: 0 0 5px rgba(0, 199, 177, 0.5);
        }
        
        button {
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            border: none;
            background-color: var(--primary-color);
            color: white;
            font-weight: bold;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        
        button:hover {
            background-color: var(--secondary-color);
        }
        
        button:disabled {
            background-color: #555555;
            cursor: not-allowed;
        }
        
        .helper-text {
            color: #bbbbbb;
            font-size: 0.85rem;
            margin-top: 0.5rem;
            font-style: italic;
        }
        
        .welcome-message {
            background-color: var(--accent-color);
            border-left: 4px solid var(--secondary-color);
            padding: 1rem;
            border-radius: 4px;
            margin-bottom: 1rem;
        }
        
        .role {
            font-size: 0.85rem;
            font-weight: bold;
            margin-bottom: 0.5rem;
        }
        
        .user-role {
            color: rgba(255, 255, 255, 0.9);
        }
        
        .bot-role {
            color: var(--primary-color);
        }
        
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(255,255,255,.3);
            border-radius: 50%;
            border-top-color: var(--primary-color);
            animation: spin 1s ease-in-out infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .status {
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 5px;
        }
        
        .status.error {
            background-color: rgba(255, 0, 0, 0.2);
            border: 1px solid rgba(255, 0, 0, 0.5);
        }
        
        .status.success {
            background-color: rgba(0, 255, 0, 0.2);
            border: 1px solid rgba(0, 255, 0, 0.5);
        }
        
        .status.info {
            background-color: rgba(0, 0, 255, 0.2);
            border: 1px solid rgba(0, 0, 255, 0.5);
        }
        
        footer {
            text-align: center;
            padding-top: 1rem;
            margin-top: 1rem;
            color: #bbbbbb;
            font-size: 0.8rem;
            border-top: 1px solid var(--border-color);
        }
        
        .progress-bar-container {
            width: 100%;
            height: 8px;
            background-color: var(--accent-color);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 10px;
            display: none;
        }
        
        .progress-bar {
            height: 100%;
            background-color: var(--primary-color);
            width: 0%;
            transition: width 0.3s ease;
        }
        
        .timeout-warning {
            color: orange;
            font-size: 0.9rem;
            margin-top: 5px;
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <img src="/static/logo.jpeg" alt="TyTuX Logo" class="logo">
            <div>
                <h1>🤖 TyTuX - Command Your Data</h1>
                <div class="caption">Connected to New Relic Account: {{ account_id }}</div>
            </div>
        </header>
        
        <div class="chat-container">
            <div id="status-container"></div>
            <div class="chat-messages" id="chat-messages">
                <div class="bot-message message">
                    <div class="role bot-role">🤖 Gemini</div>
                    <div class="message-content">
                        I'm initialized with account ID {{ account_id }}. I'll inspect the NerdGraph API schema when no specific query is provided. How can I help you today?
                    </div>
                </div>
            </div>
            
            <div class="input-container">
                <div class="input-row">
                    <input type="text" id="user-input" placeholder="Ask anything about your New Relic data..." 
                           autofocus>
                    <button id="send-button">Send</button>
                </div>
                <div class="helper-text">Press Enter or click Send to submit your query</div>
                <div class="progress-bar-container" id="progress-container">
                    <div class="progress-bar" id="progress-bar"></div>
                </div>
                <div class="timeout-warning" id="timeout-warning">This request is taking longer than usual...</div>
                <div class="input-row" style="margin-top: 10px;">
                    <button id="connect-button">Connect</button>
                    <button id="clear-button">Clear Chat</button>
                    <button id="reset-button">Reset Agent</button>
                </div>
            </div>
        </div>
        
        <footer>
            TyTuX - New Relic GraphQL Assistant | Powered by Gemini AI
        </footer>
    </div>
    
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const chatMessages = document.getElementById('chat-messages');
            const userInput = document.getElementById('user-input');
            const sendButton = document.getElementById('send-button');
            const connectButton = document.getElementById('connect-button');
            const clearButton = document.getElementById('clear-button');
            const resetButton = document.getElementById('reset-button');
            const statusContainer = document.getElementById('status-container');
            const progressContainer = document.getElementById('progress-container');
            const progressBar = document.getElementById('progress-bar');
            const timeoutWarning = document.getElementById('timeout-warning');
            
            let isProcessing = false;
            let progressTimer = null;
            let progressValue = 0;
            
            // Function to add status messages
            function showStatus(message, type = 'info') {
                const statusDiv = document.createElement('div');
                statusDiv.className = `status ${type}`;
                statusDiv.textContent = message;
                statusContainer.innerHTML = '';
                statusContainer.appendChild(statusDiv);
                
                // Auto-remove success messages after 3 seconds
                if (type === 'success') {
                    setTimeout(() => {
                        statusContainer.removeChild(statusDiv);
                    }, 3000);
                }
            }
            
            // Function to add a message to the chat
            function addMessage(content, isUser = false) {
                const messageDiv = document.createElement('div');
                messageDiv.className = isUser ? 'user-message message' : 'bot-message message';
                
                const roleDiv = document.createElement('div');
                roleDiv.className = isUser ? 'role user-role' : 'role bot-role';
                roleDiv.textContent = isUser ? '🧑 You' : '🤖 Gemini';
                
                const contentDiv = document.createElement('div');
                contentDiv.className = 'message-content';
                contentDiv.textContent = content;
                
                messageDiv.appendChild(roleDiv);
                messageDiv.appendChild(contentDiv);
                
                chatMessages.appendChild(messageDiv);
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }
            
            // Function to add a loading message
            function showLoading() {
                const loadingDiv = document.createElement('div');
                loadingDiv.className = 'bot-message message';
                loadingDiv.id = 'loading-message';
                
                const roleDiv = document.createElement('div');
                roleDiv.className = 'role bot-role';
                roleDiv.textContent = '🤖 Gemini';
                
                const contentDiv = document.createElement('div');
                contentDiv.className = 'message-content';
                
                const loadingSpinner = document.createElement('div');
                loadingSpinner.className = 'loading';
                contentDiv.appendChild(document.createTextNode('Thinking... '));
                contentDiv.appendChild(loadingSpinner);
                
                loadingDiv.appendChild(roleDiv);
                loadingDiv.appendChild(contentDiv);
                
                chatMessages.appendChild(loadingDiv);
                chatMessages.scrollTop = chatMessages.scrollHeight;
                
                // Show progress bar
                progressContainer.style.display = 'block';
                progressValue = 0;
                progressBar.style.width = '0%';
                
                // Update the progress bar
                progressTimer = setInterval(() => {
                    // Simulate progress that slows down as it approaches 100%
                    if (progressValue < 90) {
                        progressValue += (95 - progressValue) / 80;
                    } else {
                        progressValue += 0.05;
                    }
                    
                    // Cap at 95% (full completion happens when request finishes)
                    if (progressValue > 95) {
                        progressValue = 95;
                    }
                    
                    // Show timeout warning after 30 seconds
                    if (progressValue > 60 && !timeoutWarning.style.display === 'block') {
                        timeoutWarning.style.display = 'block';
                    }
                    
                    progressBar.style.width = progressValue + '%';
                }, 100);
            }
            
            // Function to remove loading message
            function hideLoading() {
                const loadingMessage = document.getElementById('loading-message');
                if (loadingMessage) {
                    chatMessages.removeChild(loadingMessage);
                }
                
                // Hide progress bar and reset
                if (progressTimer) {
                    clearInterval(progressTimer);
                    progressTimer = null;
                }
                progressContainer.style.display = 'none';
                timeoutWarning.style.display = 'none';
                progressBar.style.width = '100%';
                setTimeout(() => {
                    progressBar.style.width = '0%';
                }, 300);
            }
            
            // Function to send a message
            async function sendMessage() {
                const message = userInput.value.trim();
                if (!message || isProcessing) return;
                
                // Disable input while processing
                isProcessing = true;
                userInput.disabled = true;
                sendButton.disabled = true;
                
                // Add user message to chat
                addMessage(message, true);
                
                // Clear input field
                userInput.value = '';
                
                // Show loading animation
                showLoading();
                
                try {
                    // Set up a timeout for the request
                    const controller = new AbortController();
                    const timeoutId = setTimeout(() => controller.abort(), 65000); // 65 seconds timeout
                    
                    // Send the message to the server
                    const response = await fetch('/chat', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ message }),
                        signal: controller.signal
                    });
                    
                    // Clear the timeout
                    clearTimeout(timeoutId);
                    
                    const data = await response.json();
                    
                    // Remove loading animation
                    hideLoading();
                    
                    if (data.status === 'success') {
                        // Add bot response to chat
                        addMessage(data.response);
                    } else {
                        // Show error
                        showStatus(`Error: ${data.message}`, 'error');
                        addMessage(`I encountered an error: ${data.message}. Please try again.`);
                    }
                } catch (error) {
                    // Handle fetch error
                    hideLoading();
                    
                    if (error.name === 'AbortError') {
                        showStatus('Request timed out. The server took too long to respond.', 'error');
                        addMessage('I encountered a timeout error. Please try a simpler query or reset the agent.');
                    } else {
                        showStatus(`Network error: ${error.message}`, 'error');
                        addMessage(`I encountered a network error. Please try again.`);
                    }
                } finally {
                    // Re-enable input
                    isProcessing = false;
                    userInput.disabled = false;
                    sendButton.disabled = false;
                    userInput.focus();
                }
            }
            
            // Connect to the backend
            async function connect() {
                connectButton.disabled = true;
                connectButton.textContent = 'Connecting...';
                
                try {
                    const response = await fetch('/connect', {
                        method: 'POST'
                    });
                    
                    const data = await response.json();
                    
                    if (data.status === 'success') {
                        showStatus(`Connected: ${data.message}`, 'success');
                        connectButton.textContent = 'Connected';
                    } else {
                        showStatus(`Connection error: ${data.message}`, 'error');
                        connectButton.textContent = 'Retry Connection';
                        connectButton.disabled = false;
                    }
                } catch (error) {
                    showStatus(`Network error: ${error.message}`, 'error');
                    connectButton.textContent = 'Retry Connection';
                    connectButton.disabled = false;
                }
            }
            
            // Reset the agent
            async function resetAgent() {
                resetButton.disabled = true;
                resetButton.textContent = 'Resetting...';
                
                try {
                    const response = await fetch('/reset_agent', {
                        method: 'POST'
                    });
                    
                    const data = await response.json();
                    
                    if (data.status === 'success') {
                        showStatus('Agent has been reset. Please reconnect.', 'success');
                        connectButton.textContent = 'Connect';
                        connectButton.disabled = false;
                    } else {
                        showStatus(`Reset error: ${data.message}`, 'error');
                    }
                } catch (error) {
                    showStatus(`Network error: ${error.message}`, 'error');
                } finally {
                    resetButton.textContent = 'Reset Agent';
                    resetButton.disabled = false;
                }
            }
            
            // Clear chat history
            function clearChat() {
                // Keep only the welcome message
                while (chatMessages.childNodes.length > 1) {
                    chatMessages.removeChild(chatMessages.lastChild);
                }
                statusContainer.innerHTML = '';
            }
            
            // Event listeners
            sendButton.addEventListener('click', sendMessage);
            connectButton.addEventListener('click', connect);
            clearButton.addEventListener('click', clearChat);
            resetButton.addEventListener('click', resetAgent);
            
            userInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    sendMessage();
                }
            });
            
            // Check environment variables
            fetch('/check_env')
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        let missingVars = [];
                        for (const [key, value] of Object.entries(data.results)) {
                            if (!value.set || value.length === 0) {
                                missingVars.push(key);
                            }
                        }
                        
                        if (missingVars.length > 0) {
                            showStatus(`Missing environment variables: ${missingVars.join(', ')}. Please check your .env file.`, 'error');
                        }
                    }
                })
                .catch(error => console.error('Error checking environment:', error));
            
            // Initial connect
            connect();
            
            // Focus on input field
            userInput.focus();
        });
    </script>
</body>
</html>
""")
        
    # Create static folder for logo
    os.makedirs("static", exist_ok=True)
    
    # Copy logo.jpeg to static folder
    import shutil
    try:
        shutil.copy("logo.jpeg", "static/logo.jpeg")
        print("Logo copied to static folder")
    except Exception as e:
        print(f"Could not copy logo: {e}")
        
    print("Starting Flask server...")
    app.run(debug=True, port=5000)
