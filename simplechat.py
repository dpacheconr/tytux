import asyncio
import json
import os
import logging
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class NewRelicGeminiAgent:
    """A client for interacting with New Relic's GraphQL API using Google's Gemini model."""
    
    def __init__(self):
        """Initialize the agent with API keys and configuration."""
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.new_relic_api_key = os.getenv("NEW_RELIC_USER_API_KEY")
        self.account_id = os.getenv("NEW_RELIC_ACCOUNT_ID")
        self.endpoint = os.getenv("NEW_RELIC_API_ENDPOINT", "https://api.newrelic.com/graphql")
        
        # Initialize Gemini client
        self.genai_client = genai.Client(api_key=self.gemini_api_key)
        self.model = "gemini-2.5-pro-preview-05-06"
        self.contents = []  # Conversation history
        
        # Session initialization flag
        self.session_initialized = False
        
        # Define available tools
        self.tools = {
            "executeQuery": {
                "name": "executeQuery",
                "description": "Execute a GraphQL query against the New Relic API"
            },
            "describeDomain": {
                "name": "describeDomain",
                "description": "Get information about the schema and available GraphQL types"
            },
            "introspect": {
                "name": "introspect",
                "description": "Perform GraphQL introspection to discover the schema"
            }
        }

    async def setup_connection(self):
        """Set up connection to New Relic."""
        if self.session_initialized:
            return self
            
        try:
            # Validate API keys
            if not self.gemini_api_key or not self.new_relic_api_key:
                raise ValueError("Missing required API keys in environment variables")
                
            if not self.account_id:
                logger.warning("NEW_RELIC_ACCOUNT_ID not set in environment variables")
                
            # Add initial setup prompt with account ID
            initial_prompt = f"Use account ID {self.account_id} for ongoing queries. Inspect the NerdGraph API schema when no query is provided."
            await self.agent_loop(initial_prompt)
            
            self.session_initialized = True
            return self
        except Exception as e:
            logger.error(f"Error setting up connection: {e}")
            # Make sure we clean up properly
            await self.cleanup()
            raise e

    async def agent_loop(self, prompt: str) -> str:
        """Process a user prompt and return the response."""
        # Add the user's prompt to the conversation
        self.contents.append(types.Content(role="user", parts=[types.Part(text=prompt)]))
        
        try:
            # Create tool definitions for Gemini
            tools = types.Tool(function_declarations=[
                {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The GraphQL query to execute"
                            },
                            "variables": {
                                "type": "object",
                                "description": "Variables for the GraphQL query"
                            }
                        },
                        "required": ["query"]
                    }
                }
                for _, tool in self.tools.items()
            ])
            
            # Generate a response from Gemini
            response = await self.genai_client.aio.models.generate_content(
                model=self.model,
                contents=self.contents,
                config=types.GenerateContentConfig(
                    temperature=0,
                    tools=[tools],
                ),
            )
            self.contents.append(response.candidates[0].content)

            # Process tool calls
            turn_count = 0
            max_tool_turns = 5
            while response.function_calls and turn_count < max_tool_turns:
                turn_count += 1
                tool_response_parts = []
                
                for fc_part in response.function_calls:
                    tool_name = fc_part.name
                    args = fc_part.args or {}
                    
                    try:
                        # Execute the tool directly via HTTP
                        result = await self._execute_graphql(args.get("query", ""), args.get("variables", {}))
                        tool_response = {"result": json.dumps(result)}
                    except Exception as e:
                        tool_response = {"error": f"Tool execution failed: {type(e).__name__}: {e}"}
                    
                    tool_response_parts.append(
                        types.Part.from_function_response(
                            name=tool_name, response=tool_response
                        )
                    )
                
                # Add tool responses to conversation
                self.contents.append(types.Content(role="user", parts=tool_response_parts))
                
                # Get updated response
                response = await self.genai_client.aio.models.generate_content(
                    model=self.model,
                    contents=self.contents,
                    config=types.GenerateContentConfig(
                        temperature=1.0,
                        tools=[tools],
                    ),
                )
                self.contents.append(response.candidates[0].content)
                
            # Return final response
            if turn_count >= max_tool_turns and response.function_calls:
                return f"Response exceeded maximum of {max_tool_turns} tool calls. Partial response: {response.text}"
            return response.text
            
        except Exception as e:
            logger.error(f"Error in agent_loop: {e}")
            return f"Error processing request: {str(e)}"

    async def _execute_graphql(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute a GraphQL query directly against the New Relic API."""
        if variables is None:
            variables = {}
            
        # Add account ID to variables if not present and query contains accountId
        if 'accountId' not in variables and self.account_id:
            variables['accountId'] = self.account_id
            
        headers = {
            "Content-Type": "application/json",
            "API-Key": self.new_relic_api_key
        }
        
        payload = {
            "query": query,
            "variables": variables
        }
        
        try:
            # Use asyncio to execute the HTTP request
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=30  # Adding timeout to prevent hanging
                )
            )
            
            if response.status_code != 200:
                error_msg = f"GraphQL request failed with status code {response.status_code}"
                try:
                    error_details = response.json()
                    if 'errors' in error_details:
                        error_msg += f": {error_details['errors']}"
                except:
                    error_msg += f": {response.text}"
                raise Exception(error_msg)
                
            result = response.json()
            
            # Check for GraphQL errors even with 200 status
            if 'errors' in result:
                logger.warning(f"GraphQL returned errors: {result['errors']}")
                
            return result
            
        except requests.RequestException as e:
            raise Exception(f"Network error during GraphQL request: {str(e)}")
        except json.JSONDecodeError:
            raise Exception(f"Invalid JSON response from GraphQL endpoint")

    async def cleanup(self):
        """Clean up resources."""
        # Nothing to clean up in this implementation
        self.session_initialized = False
        logger.info("Cleanup completed successfully")

# No need for npx check in this implementation since we're using direct API calls
