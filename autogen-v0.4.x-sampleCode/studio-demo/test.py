import asyncio
import os

from autogen_agentchat.base import TaskResult
from autogen_agentchat.ui import Console
from autogenstudio.teammanager import TeamManager


async def main() -> None:
    tm = TeamManager()
    stream = tm.run_stream(task="你好", team_config="/home/azureuser/azure-ai-agent-workshop/autogen-v0.4.x-sampleCode/studio-demo/team-config.json")
    await Console(stream)

if __name__ == '__main__':
    asyncio.run(main())