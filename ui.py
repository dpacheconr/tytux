import streamlit as st
import asyncio
import os
import time
from client import MCPGeminiAgent

# Use the full page width and set dark theme
st.set_page_config(page_title="TyTuX UI", page_icon="🤖", layout="wide")

# --- Header with Logo ---
col1, col2 = st.columns([1, 6])
with col1:
    st.image("logo.jpeg", width=80)
with col2:
    st.title("🤖 TyTuX - Command Your Data")
    account_id = os.getenv("NEW_RELIC_ACCOUNT_ID")
    st.caption(f"Connected to New Relic Account: {account_id}")

# --- Chatbot style CSS ---
chat_css = '''
<style>
/* Dark theme base styles */
body, .stApp {
    background-color: #1e1e1e !important;
    color: #ffffff !important;
}

.chat-container {
    max-width: 900px;
    margin: 0 auto;
    padding: 1.5rem;
    border-radius: 10px;
    background-color: #2d2d2d;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
}

.user-msg {
    background: #00b5d1; /* New Relic blue */
    color: #ffffff;
    border-radius: 18px 18px 4px 18px;
    padding: 1em 1.5em;
    margin: 1em 0 1em auto;
    max-width: 80%;
    text-align: right;
    font-size: 1.1em;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
    word-break: break-word;
}

.assistant-msg {
    background: #333333; /* Darker background */
    color: #ffffff; /* White text for contrast */
    border-radius: 18px 18px 18px 4px;
    padding: 1em 1.5em;
    margin: 1em auto 1em 0;
    max-width: 80%;
    text-align: left;
    font-size: 1.1em;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
    border-left: 4px solid #00c7b1;
    word-break: break-word;
}

.user-role-label {
    font-size: 0.85em;
    font-weight: bold;
    margin-bottom: 0.5em;
    display: block;
    color: rgba(255, 255, 255, 0.9);
}

.assistant-role-label {
    font-size: 0.85em;
    font-weight: bold;
    margin-bottom: 0.5em;
    display: block;
    color: #00b5d1;
}

.msg-content {
    line-height: 1.5;
}

.input-container {
    background: #2d2d2d;
    padding: 20px;
    border-radius: 10px;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
    margin-top: 20px;
    border: 1px solid #444444;
}

button {
    background-color: #00b5d1 !important;
    color: white !important;
}

button.clear-btn {
    background-color: #444444 !important;
    color: #ffffff !important;
}

.stTextInput input {
    border: 2px solid #444444;
    border-radius: 8px;
    padding: 12px;
    font-size: 16px;
    background-color: #333333;
    color: #ffffff;
}

.stTextInput input:focus {
    border: 2px solid #00c7b1;
    box-shadow: 0 0 5px rgba(0, 199, 177, 0.5);
}

.helper-text {
    font-size: 0.9em;
    color: #bbbbbb;
    margin-bottom: 10px;
    font-style: italic;
}

.welcome-container {
    padding: 15px;
    background-color: #333333;
    border-left: 4px solid #00c7b1;
    border-radius: 4px;
    margin-bottom: 20px;
    color: #ffffff;
}

.tool-tip {
    font-size: 0.8em;
    color: #bbbbbb;
    margin-top: 5px;
}

/* Fix Streamlit component styles for dark theme */
.stMarkdown, .stMarkdown p {
    color: #ffffff !important;
}

h1, h2, h3, h4 {
    color: #ffffff !important;
}

.stTextInput label {
    color: #ffffff !important;
}

.stCaption {
    color: #bbbbbb !important;
}

</style>
'''
st.markdown(chat_css, unsafe_allow_html=True)

# --- Welcoming message ---
if 'first_load' not in st.session_state:
    st.session_state.first_load = True
    st.markdown(
        """
        <div class="welcome-container">
            <h3>👋 Welcome to TyTuX!</h3>
            <p>This assistant helps you interact with New Relic through natural language.</p>
            <p><b>Example queries you can try:</b></p>
            <ul>
                <li>Get all alerts using nrqlConditionsSearch</li>
            </ul>
        </div>
        """, 
        unsafe_allow_html=True
    )

# --- Session state ---
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []  # List of (role, message)
if 'agent' not in st.session_state:
    try:
        st.session_state.agent = MCPGeminiAgent()
        st.session_state.connected = False
        st.session_state.response = ""
        
        # Check for environment variables
        missing_vars = []
        for var in ["GEMINI_API_KEY", "NEW_RELIC_USER_API_KEY", "NEW_RELIC_ACCOUNT_ID"]:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            st.error(f"⚠️ Missing required environment variables: {', '.join(missing_vars)}")
            st.info("These should be defined in your .env file. Please check your configuration.")
    except Exception as e:
        st.error(f"Error initializing agent: {str(e)}")
        print(f"ERROR initializing agent: {str(e)}")
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'user_request' not in st.session_state:
    st.session_state.user_request = None  # Store the current request being processed
if 'submitted_message' not in st.session_state:
    st.session_state.submitted_message = None  # For storing messages to be processed

# Function to handle input submission and clear the field
def handle_message_submit():
    # Get the current input field key from the session state
    current_key = st.session_state.input_key
    
    # Check if the current key exists in session state and has a value
    if current_key in st.session_state and st.session_state[current_key].strip():
        # Store the message to be processed
        current_input = st.session_state[current_key].strip()
        st.session_state.user_request = current_input
        
        # Log the input for debugging
        print(f"Input submitted through on_change: {current_input}")
        
        # Clear will be handled by the key change mechanism
        st.session_state.input_key = str(time.time())  # Generate new key to force clean input
        st.session_state.processing = True

# --- Helper function for asyncio operations ---
def run_async(coro):
    """Properly run an async function from Streamlit"""
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(coro)
        print(f"Async operation completed successfully: {type(result)}")
        return result
    except Exception as e:
        print(f"Error in async operation: {e}")
        raise
    finally:
        loop.close()

# --- Chat display ---
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
if len(st.session_state.chat_history) == 0:
    # Show initial message about context
    account_id = os.getenv("NEW_RELIC_ACCOUNT_ID")
    st.markdown(f"""
        <div class='assistant-msg'>
            <span class='assistant-role-label'>🤖 Gemini</span>
            <div class='msg-content'>I'm initialized with account ID {account_id}. I'll inspect the NerdGraph API schema when no specific query is provided. How can I help you today?</div>
        </div>
    """, unsafe_allow_html=True)
    
for role, msg in st.session_state.chat_history:
    if role == 'user':
        st.markdown(f"""
            <div class='user-msg'>
                <span class='user-role-label'>🧑 You</span>
                <div class='msg-content'>{msg}</div>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
            <div class='assistant-msg'>
                <span class='assistant-role-label'>🤖 Gemini</span>
                <div class='msg-content'>{msg}</div>
            </div>
        """, unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# --- Input area ---
# Using a container instead of HTML div to avoid rendering issues
input_container = st.container()

# Determine the current input key (changes when we want to clear the input)
if 'input_key' not in st.session_state:
    st.session_state.input_key = "input_default"

with input_container:
    # Apply styles through CSS class
    st.markdown('<div style="background: #2d2d2d; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2); margin-top: 20px; border: 1px solid #444444;">', unsafe_allow_html=True)
    
    user_input = st.text_input(
        "Message Input",  # Non-empty label for accessibility
        key=st.session_state.input_key,  # Dynamic key to force reset
        placeholder="Ask anything about your New Relic data...",
        label_visibility="collapsed",
        disabled=st.session_state.processing,  # Disable while processing
        on_change=handle_message_submit
    )
    
    # Debug info for current state
    if st.session_state.processing:
        print("UI is in processing state")
    if st.session_state.user_request:
        print(f"Current user request: {st.session_state.user_request}")
    
    col1, col2, col3 = st.columns([5, 1, 1])
    with col1:
        st.markdown('<p style="font-size: 0.9em; color: #bbbbbb; margin-bottom: 10px; font-style: italic;">Press Enter or click Send to submit your query</p>', unsafe_allow_html=True)
    with col2:
        send = st.button("Send", key="send", use_container_width=True, type="primary", disabled=st.session_state.processing)
    with col3:
        clear = st.button("Clear Chat", key="clear", use_container_width=True, disabled=st.session_state.processing)
    
    st.markdown('</div>', unsafe_allow_html=True)

if clear:
    st.session_state.chat_history = []
    st.session_state.input_key = str(time.time())  # Force input reset
    st.session_state.user_request = None
    st.session_state.processing = False
    st.rerun()

# Process new user input - only take action if we have a non-empty input and not already processing
if ((send or user_input.strip()) and not st.session_state.processing and user_input.strip()):
    current_input = user_input.strip()
    print(f"Processing input from button/direct entry: {current_input}")
    
    # Add to chat history
    st.session_state.chat_history.append(("user", current_input))
    
    # Save the request
    st.session_state.user_request = current_input
    
    # Set processing flag
    st.session_state.processing = True
    
    # Force input reset
    st.session_state.input_key = str(time.time())
    
    # Rerun to update UI with disabled inputs
    st.rerun()

# Process the pending request
if st.session_state.processing and st.session_state.user_request:
    with st.spinner("Gemini is thinking..."):
        current_request = st.session_state.user_request  # Get the saved request
        st.session_state.user_request = None  # Clear request to prevent reprocessing
        answer = None
        
        try:
            if not st.session_state.connected:
                run_async(st.session_state.agent.connect())
                st.session_state.connected = True
            
            # Process the request with additional error handling
            print("Sending request to agent_loop...")
            try:
                response = run_async(st.session_state.agent.agent_loop(current_request))
                print(f"Got response from agent_loop, type: {type(response)}")
            except Exception as e:
                print(f"CRITICAL ERROR in agent_loop call: {str(e)}")
                response = None
            
            # If response is None, handle it gracefully
            if response is None:
                print("WARNING: agent_loop returned None")
                answer = "I'm sorry, I couldn't generate a response. Please try again."
            else:
                # Try to get text from Gemini's response
                try:
                    # Check if response has candidates attribute (direct Gemini response)
                    if hasattr(response, 'candidates') and response.candidates:
                        print("Response has candidates, extracting from there...")
                        answer = response.candidates[0].content.text
                        print(f"Extracted answer from candidates: {answer[:50]}...")
                    # Check if it has a text attribute
                    elif hasattr(response, 'text'):
                        print("Response has text attribute, using that...")
                        answer = response.text
                        print(f"Extracted answer from text attribute: {answer[:50]}...")
                    # Fallback to string representation
                    else:
                        print(f"No recognized response format, using string representation")
                        answer = str(response)
                        print(f"String representation: {answer[:50]}...")
                except Exception as e:
                    print(f"Error extracting text from response: {e}")
                    answer = f"Error processing response: {str(e)}"
        except Exception as e:
            print(f"Error in agent_loop: {e}")
            answer = f"Error processing your request: {str(e)}"
        
        # Add answer to chat history
        st.session_state.chat_history.append(("assistant", answer))
        
        # Reset processing state
        st.session_state.processing = False
    st.rerun()

# --- Footer ---
st.markdown("""
<div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #444444;">
    <p style="color: #bbbbbb; font-size: 0.8em;">TyTuX - New Relic GraphQL Assistant | Powered by Gemini AI</p>
</div>
""", unsafe_allow_html=True)
