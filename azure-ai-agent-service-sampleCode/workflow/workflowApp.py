import asyncio
import logging
import os
import aiohttp

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
        "name": "tellHaikuWorkflow",
        "Variables": [
            {"Type": "messages", "Name": "HaikuOutput"},
            {"Type": "thread",   "Name": "HaikuThread"}
        ],
        "States": [
            {
                "Name": "TellHaiku",
                "Actors": [
                    {
                        "Agent": assistant_name,
                        "AgentId": assistant_id,
                        "HumanInLoopMode": "Always",
                        "StreamOutput": True,
                        "MessagesOut": "HaikuOutput",
                        "Thread": "HaikuThread"
                    }
                ]
            },
            {"Name": "End", "IsFinal": True}
        ],
        "StartState": "TellHaiku",
        "Transitions": [
            {"From": "TellHaiku", "To": "End", "Condition": "HaikuOutput.Contains('Haiku')"}
        ]
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

# New method to trigger a workflow run on a specific thread
async def create_thread_run(
    workflow_base_url: str,  # e.g. "{{workflowBaseUrl}}"
    thread_id: str,          # e.g. "{{thread.id}}"
    workflow_id: str         # e.g. "{{workflow.id}}"
) -> dict:
    """
    Trigger a run for a workflow thread via POST /threads/{thread_id}/runs.
    """
    token = await fetch_token()
    payload = {"assistant_id": workflow_id}
    async with aiohttp.ClientSession() as session:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        url = f"{workflow_base_url.rstrip('/')}/threads/{thread_id}/runs"
        async with session.post(url, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()


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

        student_agent, teacher_agent, thread = await initialize()

        # 测试 create_workflow，使用 student_agent 和默认认证方式
        workflow_url = os.getenv("WORKFLOW_BASE_URL")
        print("Creating sample workflow for Haiku...")
        workflow_result = await create_workflow(
            workflow_url,
            student_agent.name,
            student_agent.id
        )
        print(f"Workflow created: {workflow_result}")

        # 测试 create_thread_run，使用 student_agent 和默认认证方式
        print("Creating thread run for workflow...")
        thread_run_result = await create_thread_run(
            workflow_url,
            thread.id,
            workflow_result["id"]
        )
        print(f"Thread run created: {thread_run_result}")

        # while True:
        #     # Get user input prompt in the terminal using a pretty shade of green
        #     print("\n")
        #     prompt = input(f"what's 1 and 1?")
        #     if prompt.lower() == "exit":
        #         break
        #     if not prompt:
        #         continue
        #     await post_message(agent=student_agent, thread_id=thread.id, content=prompt, thread=thread)

if __name__ == "__main__":
    print("Starting async program...")
    asyncio.run(main())
    print("Program finished.")
