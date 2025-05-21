import asyncio
import json
import os
from typing import List, Optional
from contextlib import AsyncExitStack
import warnings

from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv
import subprocess
import streamlit as st

print("Loading environment variables from .env file")
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    print(f".env file found at {dotenv_path}")
    # Load with verbose output
    load_dotenv(dotenv_path=dotenv_path, verbose=True)
else:
    print(f"WARNING: .env file not found at {dotenv_path}")
    load_dotenv()
    
warnings.filterwarnings("ignore", category=ResourceWarning)

# Check for required environment variables
required_vars = ["GEMINI_API_KEY", "NEW_RELIC_USER_API_KEY", "NEW_RELIC_ACCOUNT_ID"]
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    print(f"ERROR: Missing required environment variables: {', '.join(missing_vars)}")
    print("Please ensure these are set in your .env file or environment")

class MCPGeminiAgent:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = "gemini-2.0-flash"
        self.tools = None
        self.server_params = None
        self.server_name = None
        
        # Initialize conversation with a default context
        account_id = os.getenv("NEW_RELIC_ACCOUNT_ID")
        initial_prompt = f"Use account ID {account_id} for ongoing queries. Inspect the NerdGraph API schema, keep it in memory and when no query is provided use the schema to build a query."
        self.contents = [types.Content(role="user", parts=[types.Part(text=initial_prompt)])]
        
        # Create a dummy response to add to history
        self.contents.append(types.Content(role="model", parts=[types.Part(text=f"I'll use account ID {account_id} for queries and use NerdGraph API schema to build a query when no specific query is provided.")]))

    async def connect(self):
        headers = {
            "API-Key": os.getenv("NEW_RELIC_USER_API_KEY"),
            "Content-Type": "application/json"
        }
        endpoint = os.getenv("NEW_RELIC_API_ENDPOINT", "https://api.newrelic.com/graphql")
        mutations = os.getenv("ALLOW_MUTATIONS", "false").lower() 
         
        mcp_config= {
            "mcpServers": {
                "graphql": {
                "command": "npx",
                "args": ["mcp-graphql"],
                "env": {
                            "ENDPOINT": endpoint,
                            "HEADERS": json.dumps(headers),
                            "NODE_OPTIONS": "--disable-warning=ExperimentalWarning",
                            "ALLOW_MUTATIONS": str(mutations)
                        }
                }
            }
        }
        
        servers = mcp_config['mcpServers']
        server_name, server_cfg = next(iter(servers.items()))  # Automatically select the first server
        self.server_name = server_name
        command = server_cfg['command']
        args = server_cfg.get('args', [])
        env = server_cfg.get('env', None)
        self.server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env
        )
        
        self.stdio_transport = await self.exit_stack.enter_async_context(stdio_client(self.server_params))
        self.stdio, self.write = self.stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        await self.session.initialize()
        print(f"Successfully connected to: {self.server_name}")

    async def agent_loop(self, prompt: str) -> str:
        # Add debugging to identify and fix the None return issue
        print(f"Agent loop started with prompt: {prompt[:50]}...")
        
        # Add the user's prompt to the conversation
        self.contents.append(types.Content(role="user", parts=[types.Part(text=prompt)]))
        
        # List available tools for this server
        print("Fetching available tools...")
        mcp_tools = await self.session.list_tools()
        tools = types.Tool(function_declarations=[
            {
                "name": tool.name,
                "description": tool.description,
            }
            for tool in mcp_tools.tools
        ])
        self.tools = tools

        # Generate a response from Gemini with enhanced error handling
        print("Generating initial response from Gemini...")
        try:
            # Verify API key is available
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                print("ERROR: GEMINI_API_KEY environment variable is not set")
                raise ValueError("Gemini API key is missing. Please set the GEMINI_API_KEY environment variable.")
                
            # Log model being used
            print(f"Using Gemini model: {self.model}")
            
            # Attempt to generate content with detailed logging
            try:
                response = await self.genai_client.aio.models.generate_content(
                    model=self.model,
                    contents=self.contents,
                    config=types.GenerateContentConfig(
                        temperature=0,
                        tools=[tools],
                    ),
                )
                print(f"Initial response received, type: {type(response)}")
                
                # Verify response has expected structure
                if not hasattr(response, 'candidates') or not response.candidates:
                    print("WARNING: Response missing candidates")
                    raise ValueError("Gemini response missing expected 'candidates' attribute")
                    
                # Add the response to conversation history
                self.contents.append(response.candidates[0].content)
                
            except Exception as api_error:
                print(f"ERROR during Gemini API call: {type(api_error).__name__}: {str(api_error)}")
                raise api_error
                
        except Exception as e:
            print(f"ERROR: Failed to generate content from Gemini: {str(e)}")
            # Create a minimal response object to avoid returning None
            class SimpleResponse:
                def __init__(self, error_message):
                    self.text = error_message
                    self.function_calls = []
            return SimpleResponse(f"Error calling Gemini API: {str(e)}")

        turn_count = 0
        max_tool_turns = 5
        while response.function_calls and turn_count < max_tool_turns:
            turn_count += 1
            tool_response_parts: List[types.Part] = []
            for fc_part in response.function_calls:
                tool_name = fc_part.name
                args = fc_part.args or {}
                print(f"Invoking MCP tool '{tool_name}' with arguments: {args}")
                tool_response: dict
                try:
                    tool_result = await self.session.call_tool(tool_name, args)
                    print(f"Tool '{tool_name}' executed.")
                    if tool_result.isError:
                        tool_response = {"error": tool_result.content[0].text}
                    else:
                        tool_response = {"result": tool_result.content[0].text}
                except Exception as e:
                    tool_response = {"error":  f"Tool execution failed: {type(e).__name__}: {e}"}
                tool_response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name, response=tool_response
                    )
                )
            self.contents.append(types.Content(role="user", parts=tool_response_parts))  # Add tool responses
            print(f"Added {len(tool_response_parts)} tool response(s) to the conversation.")
            print("Requesting updated response from Gemini...")
            try:
                response = await self.genai_client.aio.models.generate_content(
                    model=self.model,
                    contents=self.contents,
                    config=types.GenerateContentConfig(
                        temperature=1.0,
                        tools=[tools],
                    ),
                )
                print("Updated response received successfully")
                if hasattr(response, 'candidates') and response.candidates:
                    self.contents.append(response.candidates[0].content)  # Add updated Gemini response
                else:
                    print("WARNING: Updated response missing candidates")
            except Exception as update_error:
                print(f"ERROR during updated response: {str(update_error)}")
                # Continue with last valid response
        if turn_count >= max_tool_turns and response.function_calls:
            print(f"Stopped after {max_tool_turns} tool calls to avoid infinite loops.")
        print("All tool calls complete. Displaying Gemini's final response.")
        
        # Structure the response to include the text directly
        print("Final response processing...")
        try:
            # Add a text property to make it easier for the UI to extract the content
            # Defensive programming - create a fallback if response is None somehow
            if response is None:
                print("WARNING: Response is None in final processing")
                class EmptyResponse:
                    def __init__(self):
                        self.candidates = []
                        self.function_calls = []
                response = EmptyResponse()
                response_obj = response
                response_text = "I didn't receive a proper response. Please try again."
            else:
                response_obj = response
                try:
                    if hasattr(response, 'candidates') and response.candidates:
                        response_text = response.candidates[0].content.text
                    else:
                        print("WARNING: Response missing expected structure")
                        response_text = "I received an incomplete response. Please try again."
                    print(f"Successfully extracted response text: {response_text[:50]}...")
                except Exception as e:
                    print(f"Error extracting text from response: {e}")
                    response_text = "I encountered an error processing the response. Please try again."
            
            # Set the text property - this is what the UI looks for
            setattr(response_obj, 'text', response_text)
            print("Final response object prepared with text property")
            return response_obj
            
        except Exception as final_e:
            print(f"ERROR in final response preparation: {str(final_e)}")
            # Always return something usable
            class FallbackResponse:
                def __init__(self, message):
                    self.text = message
                    self.candidates = []
                    self.function_calls = []
            
            fallback = FallbackResponse(f"I encountered an error: {str(final_e)}. Please try again.")
            print("Returning fallback response object")
            return fallback

    async def chat(self):
        print(f"\nMCP-Gemini Assistant is ready and connected to: {self.server_name}")
        print("Enter your question below, or type 'quit' to exit.")
        while True:
            try:
                query = input("\nYour query: ").strip()
                if query.lower() == 'quit':
                    print("Session ended. Goodbye!")
                    break
                print(f"Processing your request...")
                res = await self.agent_loop(query)
                print("\nGemini's answer:")
                print(res.text)
            except KeyboardInterrupt:
                print("\nSession interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\nAn error occurred: {str(e)}")

    async def cleanup(self):
        await self.exit_stack.aclose()

async def main():
    agent = MCPGeminiAgent()
    try:
        await agent.connect()
        await agent.chat()
    finally:
        await agent.cleanup()

def is_npx_installed():
    try:
        # Run the `npx --version` command
        result = subprocess.run(["npx", "--version"], check=True, text=True, capture_output=True)
        print(f"npx is installed. Version: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("npx is not installed.")
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error while checking npx: {e.stderr}")
        return False

def run_streamlit_agent():
    import asyncio
    import threading
    import queue

    st.set_page_config(page_title="TyTuX UI", page_icon="🤖")
    st.title("🤖 TyTuX - Command Your Data")
    st.markdown("""
    Welcome to TyTuX! This is a very basic UI to interact with your assistant.
    - Enter your prompt below and click **Send** to interact with the backend.
    """)

    if 'agent' not in st.session_state:
        st.session_state.agent = MCPGeminiAgent()
        st.session_state.connected = False
        st.session_state.loop = asyncio.new_event_loop()
        st.session_state.response = ""

    user_input = st.text_area("Your prompt:", height=100)
    send = st.button("Send")

    if send and user_input.strip():
        if not st.session_state.connected:
            with st.spinner("Connecting to backend..."):
                st.session_state.loop.run_until_complete(st.session_state.agent.connect())
                st.session_state.connected = True
        with st.spinner("Processing..."):
            response = st.session_state.loop.run_until_complete(
                st.session_state.agent.agent_loop(user_input)
            )
            # Try to get text from Gemini's response
            try:
                st.session_state.response = response.text
            except Exception:
                st.session_state.response = str(response)
    if st.session_state.response:
        st.markdown(f"**Gemini's answer:**\n\n{st.session_state.response}")

if __name__ == "__main__":
    import sys
    import os
    if len(sys.argv) > 1 and sys.argv[1] == "ui":
        run_streamlit_agent()
    else:
        print("TyTuX - Command your data")
        if is_npx_installed():
            pass
        else:
            print("Please install npx (Node.js) to proceed.")
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("Session interrupted. Goodbye!")
        finally:
            sys.stderr = open(os.devnull, "w")