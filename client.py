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

load_dotenv()
warnings.filterwarnings("ignore", category=ResourceWarning)

class MCPGeminiAgent:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = "gemini-2.0-flash"
        self.tools = None
        self.server_params = None
        self.server_name = None
        self.contents = []  # Initialize conversation history for Gemini

    async def connect(self):
        headers = {
            "API-Key": os.getenv("NEW_RELIC_USER_API_KEY"),
            "Content-Type": "application/json"
        }
        endpoint = os.getenv("NEW_RELIC_API_ENDPOINT", "https://api.newrelic.com/graphql")
        mcp_config= {
            "mcpServers": {
                "graphql": {
                "command": "npx",
                "args": ["mcp-graphql"],
                "env": {
                            "ENDPOINT": endpoint,
                            "HEADERS": json.dumps(headers),
                            "NODE_OPTIONS": "--disable-warning=ExperimentalWarning"
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
        # Add the user's prompt to the conversation
        self.contents.append(types.Content(role="user", parts=[types.Part(text=prompt)]))
        
        # List available tools for this server
        mcp_tools = await self.session.list_tools()
        tools = types.Tool(function_declarations=[
            {
                "name": tool.name,
                "description": tool.description,
            }
            for tool in mcp_tools.tools
        ])
        self.tools = tools

        # Generate a response from Gemini
        response = await self.genai_client.aio.models.generate_content(
            model=self.model,
            contents=self.contents,
            config=types.GenerateContentConfig(
                temperature=0,
                tools=[tools],
            ),
        )
        self.contents.append(response.candidates[0].content)  # Add Gemini's response to the conversation

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
            response = await self.genai_client.aio.models.generate_content(
                model=self.model,
                contents=self.contents,
                config=types.GenerateContentConfig(
                    temperature=1.0,
                    tools=[tools],
                ),
            )
            self.contents.append(response.candidates[0].content)  # Add updated Gemini response
        if turn_count >= max_tool_turns and response.function_calls:
            print(f"Stopped after {max_tool_turns} tool calls to avoid infinite loops.")
        print("All tool calls complete. Displaying Gemini's final response.")
        return response

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

if __name__ == "__main__":
    import sys
    import os
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