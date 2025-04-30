import asyncio
import logging
import os
import aiohttp
import json
import time

from azure.ai.projects.aio import AIProjectClient
from azure.ai.projects.models import (
    Agent,
    AgentThread,
    AsyncToolSet
)
from azure.identity import DefaultAzureCredential
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace

from dotenv import load_dotenv
load_dotenv('/Users/huqianghui/Downloads/1.github/azure-ai-agent-workshop/.env')


logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

TENTS_DATA_SHEET_FILE = "/home/azureuser/azure-ai-agent-workshop/azure-ai-agent-service-sampleCode/datasheet/contoso-tents-datasheet.pdf"
API_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT")
PROJECT_CONNECTION_STRING = os.environ["PROJECT_CONNECTION_STRING"]
BING_CONNECTION_NAME = os.getenv("BING_CONNECTION_NAME")
MAX_COMPLETION_TOKENS = 4096
MAX_PROMPT_TOKENS = 10240
TEMPERATURE = 0.2

toolset = AsyncToolSet()

project_client = AIProjectClient.from_connection_string(
    credential=DefaultAzureCredential(),
    conn_str=PROJECT_CONNECTION_STRING,
)


async def initialize() -> tuple[Agent,Agent, AgentThread]:

    try:
        # make sure the agent in the flow exists 
        print("getting student agent...")
        student_agent = await project_client.agents.get_agent(assistant_id="asst_kHtgdIbuumzyOmnZ9JVhc3MV")
        teacher_agent = await project_client.agents.get_agent(assistant_id="asst_rx0aXVop7mOuWzpLUgVWbXtl")
        print("Creating thread...")
        thread = await project_client.agents.create_thread()
        print(f"Created thread, ID: {thread.id}")

        return student_agent,teacher_agent, thread

    except Exception as e:
        logger.error("An error occurred initializing the agent: %s", str(e))


async def cleanup(agent: Agent, thread: AgentThread) -> None:
    """Cleanup the resources."""
    await project_client.agents.delete_thread(thread.id)
    await project_client.agents.delete_agent(agent.id)


async def post_message(thread_id: str, content: str, agent: Agent, thread: AgentThread) -> None:
    """Post a message to the Azure AI Agent Service."""
    try:
        await project_client.agents.create_message(
            thread_id=thread_id,
            role="user",
            content=content)

    except Exception as e:
        (f"An error occurred posting the message: {str(e)}")


async def fetch_token():
    credential = DefaultAzureCredential()
    scope = "https://management.azure.com/.default"
    token = credential.get_token(scope).token
    credential.close()
    return token

async def create_workflow(
    workflow_base_url: str,  # e.g. "{{workflowBaseUrl}}"
    assistant_name: str,     # e.g. "{{assistant.name}}"
    assistant_id: str        # e.g. "{{assistant.id}}"
) -> dict:
    """
    Create a new workflow via HTTP POST. Uses DefaultAzureCredential for auth.
    """
    token = await fetch_token()

    payload = {
    "name": "AsusWorkflow",
    "states": [
        {
            "name": "Master",
            "actors": [
                {
                    "agent": "MasterAgent",
                    "streamOutput": True,
                    "messagesIn": [
                        "CustomerInquery",
                        "ProductInfoOutput",
                        "IntentsOutput",
                        "ProductRecommendationOutput"
                    ],
                    "messagesOut": "MasterOutput",
                    "humanInLoopMode": "onNoMessage"
                }
            ]
        },
        {
            "name": "Intents",
            "actors": [
                {
                    "agent": "IntentsAgent",
                    "streamOutput": True,
                    "messagesIn": [
                        "MasterOutput"
                    ],
                    "messagesOut": "IntentsOutput",
                    "humanInLoopMode": "never"
                }
            ]
        },
        {
            "name": "ProductInfo",
            "actors": [
                {
                    "agent": "ProductInfoAgent",
                    "streamOutput": True,
                    "messagesIn": [
                        "MasterOutput",
                        "IntentsOutput"
                    ],
                    "messagesOut": "ProductInfoOutput",
                    "humanInLoopMode": "never"
                }
            ]
        },
        {
            "name": "ProductRecommendation",
            "actors": [
                {
                    "agent": "RecommendationAgent",
                    "streamOutput": True,
                    "messagesIn": [
                        "MasterOutput",
                        "IntentsOutput"
                    ],
                    "messagesOut": "ProductRecommendationOutput",
                    "humanInLoopMode": "never"
                }
            ]
        },
        {
            "name": "End",
            "isFinal": True
        }
    ],
    "transitions": [
        {
            "from": "Master",
            "to": "End",
            "condition": "MasterOutput.Contains('<finish>')"
        },
        {
            "from": "Master",
            "to": "Intents",
            "condition": "MasterOutput.Contains('<intent>')"
        },
        {
            "from": "Master",
            "to": "ProductInfo",
            "condition": "MasterOutput.Contains('<ProductInfo>')"
        },
        {
            "from": "ProductInfo",
            "to": "Master"
        },
        {
            "from": "Master",
            "to": "ProductRecommendation",
            "condition": "MasterOutput.Contains('<ProductRecommendation>')"
        },
        {
            "from": "ProductRecommendation",
            "to": "Master"
        }
    ],
    "variables": [
        {
            "Type": "messages",
            "name": "CustomerInquery"
        },
        {
            "Type": "messages",
            "name": "IntentsOutput"
        },
        {
            "Type": "messages",
            "name": "ProductRecommendationOutput"
        },
        {
            "Type": "messages",
            "name": "ProductInfoOutput"
        },
        {
            "Type": "messages",
            "name": "MasterOutput"
        }
    ],
    "startstate": "Master"
}

    async with aiohttp.ClientSession() as session:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        url = f"{workflow_base_url.rstrip('/')}/agents"
        async with session.post(url, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()

# New method to get the status and results of a workflow run
async def get_run_status(
    workflow_base_url: str,
    thread_id: str,
    run_id: str
) -> dict:
    """
    Get the status of a workflow run.
    """
    token = await fetch_token()
    
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {token}"
        }
        url = f"{workflow_base_url.rstrip('/')}/threads/{thread_id}/runs/{run_id}"
        async with session.get(url, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()

# New method to get the messages from a thread
async def get_thread_messages(
    agent_base_url: str,
    thread_id: str
) -> dict:
    """
    Get messages from a thread.
    """
    token = await fetch_token()
    
    async with aiohttp.ClientSession() as session:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        url = f"{agent_base_url.rstrip('/')}/threads/{thread_id}/messages?api-version=2024-10-21"
        async with session.get(url, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()

# Modified create_thread_run to accept custom message
async def create_thread_run(
    workflow_base_url: str,
    workflow_id: str,
    user_message: str = "請問 ROG Zephyrus G16 (2025) GU605 規格是什麼？"
) -> dict:
    """
    Trigger a run for a workflow thread via POST /threads/runs.
    """
    token = await fetch_token()
    payload = {"assistant_id": workflow_id,
               "thread": {
                    "messages": [
                    {"role": "user", "content": user_message},
                    ]}
                }
    async with aiohttp.ClientSession() as session:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        url = f"{workflow_base_url.rstrip('/')}/threads/runs"
        async with session.post(url, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()

# New function to add a message to an existing thread and create a run
async def add_message_and_run(
    workflow_base_url: str,
    agent_base_url: str,
    workflow_id: str,
    thread_id: str,
    user_message: str
) -> dict:
    """
    Add a message to an existing thread and create a new run.
    First retrieves the message history to ensure full context is maintained.
    """
    token = await fetch_token()
    
    # First retrieve existing messages to maintain context
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {token}"
        }
        url = f"{agent_base_url.rstrip('/')}/threads/{thread_id}/messages?api-version=2024-10-21"
        async with session.get(url, headers=headers) as resp:
            resp.raise_for_status()
            existing_messages = await resp.json()
            print(f"Retrieved {len(existing_messages.get('data', []))} existing messages from thread")
    
    # Now add the new message to the thread
    async with aiohttp.ClientSession() as session:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        message_payload = {
            "role": "user",
            "content": user_message
        }
        url = f"{agent_base_url.rstrip('/')}/threads/{thread_id}/messages?api-version=2024-10-21"
        async with session.post(url, headers=headers, json=message_payload) as resp:
            resp.raise_for_status()
            message_result = await resp.json()
    
    # Then create a new run on the existing thread
    async with aiohttp.ClientSession() as session:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        run_payload = {
            "assistant_id": workflow_id
        }
        url = f"{workflow_base_url.rstrip('/')}/threads/{thread_id}/runs"
        async with session.post(url, headers=headers, json=run_payload) as resp:
            resp.raise_for_status()
            return await resp.json()

# Helper function to wait for run completion
async def wait_for_run_completion(workflow_base_url: str, thread_id: str, run_id: str, poll_interval: int = 2):
    """
    Poll the run status until it's completed.
    Returns the final run status.
    """
    while True:
        run_status = await get_run_status(workflow_base_url,thread_id, run_id)
        status = run_status.get('status')
        
        if status in ['completed', 'failed', 'cancelled', 'expired']:
            return run_status
        
        print(f"Run status: {status}...")
        await asyncio.sleep(poll_interval)

# Helper function to display assistant messages in a readable format
def display_thread_messages(messages):
    """
    Display thread messages in a nice format.
    """
    if not messages or 'data' not in messages:
        print("No messages found")
        return
    
    for msg in messages['data']:
        role = msg.get('role', 'unknown')
        content = msg.get('content', [])
        
        if role == "assistant":
            print("\n\033[94m[Assistant]:\033[0m")
        else:
            print(f"\n\033[92m[{role.capitalize()}]:\033[0m")
        
        for item in content:
            if item.get('type') == 'text':
                print(item.get('text', {}).get('value', ''))


async def main() -> None:
    """
    Main function to run the agent.
    Example questions: Sales by region, top-selling products, total shipping costs by region, show as a pie chart.
    """
    # Enable Azure Monitor tracing
    application_insights_connection_string = await project_client.telemetry.get_connection_string()
    if not application_insights_connection_string:
        print("Application Insights was not enabled for this project.")
        print("Enable it via the 'Tracing' tab in your AI Foundry project page.")
        exit()
    configure_azure_monitor(connection_string=application_insights_connection_string)

    scenario = os.path.basename(__file__)
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span(scenario):
        # student_agent, teacher_agent, thread = await initialize()
        workflow_url = os.getenv("WORKFLOW_BASE_URL")
        agent_url = os.getenv("AGENT_BASE_URL")
        workflow_id = "wf_agent_ab9BNcaKrmGxM4fnJMoTDRNN"  # Your workflow ID

        # Variables to track conversation state
        current_thread_id = None

        # Interactive mode for workflow runs
        print("\n\033[1m=== Workflow Interactive Runner ===\033[0m")
        print("Type 'exit' to quit, 'new' to start a new conversation, or enter your question.")
        
        while True:
            user_input = input("\n\033[93mEnter your question: \033[0m")
            
            if user_input.lower() == 'exit':
                break
                
            if not user_input.strip():
                continue

            # Check if user wants to start a new conversation
            if user_input.lower() == 'new':
                current_thread_id = None
                print("Starting a new conversation thread.")
                continue
            
            try:
                run_id = None
                
                if current_thread_id is None:
                    # No existing thread, create a new one
                    print("\nCreating new thread and workflow run...")
                    thread_run_result = await create_thread_run(
                        workflow_url,
                        workflow_id,
                        user_input
                    )
                    
                    run_id = thread_run_result.get('id')
                    current_thread_id = thread_run_result.get('thread_id')
                    print(f"New thread created with ID: {current_thread_id}")
                    print(f"Thread run created with ID: {run_id}")
                else:
                    # Continue with existing thread
                    print(f"\nContinuing conversation in existing thread: {current_thread_id}")
                    thread_run_result = await add_message_and_run(
                        workflow_url,
                        agent_url,
                        workflow_id,
                        current_thread_id,
                        user_input
                    )
                    
                    run_id = thread_run_result.get('id')
                    print(f"Added message to existing thread and created run: {run_id}")
                
                # Wait for the run to complete
                print("Waiting for workflow to complete...")
                final_status = await wait_for_run_completion(workflow_url, current_thread_id, run_id)
                print(f"Run completed with status: {final_status.get('status')}")
                
                # Get and display the thread messages
                print("\nGetting workflow results...")
                thread_messages = await get_thread_messages(agent_url, current_thread_id)
                print("\n\033[1m=== Workflow Results ===\033[0m")
                display_thread_messages(thread_messages)
                
            except Exception as e:
                print(f"Error running workflow: {e}")
                print("Starting a new thread for next input.")
                current_thread_id = None

if __name__ == "__main__":
    print("Starting async program...")
    asyncio.run(main())
    print("Program finished.")
