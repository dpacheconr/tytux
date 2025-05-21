from quart import Quart, render_template, request, jsonify
import asyncio
from simplechat import NewRelicGeminiAgent
import os
import signal
import re

def format_response_with_markdown(response):
    """Format the response with enhanced Markdown for better readability."""
    if not response:
        return "No response received."
    
    # Add a greeting at the beginning if not present
    if not response.startswith(('Hi', 'Hello', '#', '##', '###')):
        greeting = "### Here's what I found:\n\n"
        response = greeting + response
        
    # Enhance code blocks if they don't have language specification
    response = re.sub(r'```(?!\w+\n)([^`]+)```', r'```json\n\1```', response)
    
    # Make field names bold in JSON responses
    response = re.sub(r'"(\w+)":', r'"**\1**":', response)
    
    # Add emoji for different response types
    if "error" in response.lower():
        response = response.replace("Error:", "Error: ❌")
    elif "success" in response.lower():
        response = response.replace("Success", "Success ✅")
    
    # Add dividers between sections if there are multiple sections
    if response.count('#') > 1:
        response = response.replace('##', '\n---\n##')
    
    # Add a helpful prompt at the end
    response += "\n\n---\n*You can ask follow-up questions or try another query.*"
    
    return response

# Global variables
agent = None
messages = []

# Initialize Flask app
app = Quart(__name__)

# Create templates directory if it doesn't exist
os.makedirs('templates', exist_ok=True)

@app.route('/')
async def index():
    """Serve the main chat interface."""
    return await render_template('simple.html')

@app.route('/messages')
async def get_messages():
    """Get all messages in the chat history."""
    global messages
    return jsonify({'messages': messages})

@app.route('/chat', methods=['POST'])
async def chat():
    """Process a chat message."""
    global agent, messages
    
    data = await request.get_json()
    user_message = data.get('message', '')
    
    # Add user message to history
    messages.append({'role': 'user', 'content': user_message})
    
    # Initialize agent if needed
    if agent is None:
        try:
            agent = NewRelicGeminiAgent()
            await agent.setup_connection()
        except Exception as e:
            error_message = f"Failed to initialize agent: {str(e)}"
            messages.append({'role': 'assistant', 'content': error_message})
            return jsonify({'response': error_message})
    
    # Process message
    try:
        response = await agent.agent_loop(user_message)
        
        # Format response with Markdown enhancements
        enhanced_response = format_response_with_markdown(response)
        
        messages.append({'role': 'assistant', 'content': enhanced_response})
        return jsonify({'response': enhanced_response})
    except Exception as e:
        error_message = f"### Error 😕\n\n```\n{str(e)}\n```\n\nPlease try again with a different query."
        messages.append({'role': 'assistant', 'content': error_message})
        
        # Try to reinitialize agent on failure
        if agent is not None:
            try:
                await agent.cleanup()
            except Exception as cleanup_err:
                print(f"Error during cleanup: {cleanup_err}")
            agent = None
            
        return jsonify({'response': error_message})

@app.route('/schema', methods=['POST'])
async def get_schema():
    """Get the NerdGraph API schema."""
    global agent, messages
    
    # Initialize agent if needed
    if agent is None:
        agent = NewRelicGeminiAgent()
        await agent.setup_connection()
    
    try:
        introspection_query = """
        query {
          __schema {
            queryType { name }
            mutationType { name }
            types {
              kind
              name
              description
              fields {
                name
                description
                type {
                  name
                  kind
                }
              }
            }
          }
        }
        """
        
        result = await agent._execute_graphql(introspection_query)
        
        # Add a prompt to analyze the schema
        analysis_prompt = "I've fetched the NerdGraph API schema. Format your response as markdown with headings, lists, and code blocks to explain the main query types and what they do."
        
        response = await agent.agent_loop(analysis_prompt)
        enhanced_response = format_response_with_markdown(response)
        messages.append({'role': 'assistant', 'content': enhanced_response})
        
        return jsonify({'response': enhanced_response})
    except Exception as e:
        error_message = f"### Error Fetching Schema 📊❌\n\n```\n{str(e)}\n```\n\nThere was a problem retrieving the API schema. Please check your API credentials and network connection."
        messages.append({'role': 'assistant', 'content': error_message})
        return jsonify({'response': error_message})

@app.route('/clear', methods=['POST'])
async def clear_chat():
    """Clear the chat history."""
    global messages
    messages = []
    return jsonify({'status': 'success'})

async def cleanup_on_shutdown():
    """Cleanup function to be called when server shuts down."""
    global agent
    if agent:
        try:
            print("Cleaning up agent resources...")
            await agent.cleanup()
            agent = None
            print("Agent cleanup completed")
        except Exception as e:
            print(f"Error during agent cleanup: {e}")

if __name__ == '__main__':
    import hypercorn.asyncio
    
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    
    # Register cleanup for different signals
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.ensure_future(cleanup_on_shutdown())
        )
    
    config = hypercorn.Config()
    config.bind = ["localhost:8000"]
    try:
        print("Starting TyTuX simplechat server at http://localhost:8000")
        asyncio.run(hypercorn.asyncio.serve(app, config))
    finally:
        # Make sure we clean up if the server exits
        if loop.is_running():
            loop.run_until_complete(cleanup_on_shutdown())
        print("Server shutdown complete")
