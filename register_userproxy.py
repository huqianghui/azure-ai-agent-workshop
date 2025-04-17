import asyncio

from autogen_agentchat.agents import UserProxyAgent
from autogen_core._agent_id import AgentId  # 确保 AgentId 的来源正确
from autogen_core._single_threaded_agent_runtime import SingleThreadedAgentRuntime


async def main():
    runtime = SingleThreadedAgentRuntime()
    # 直接创建 UserProxyAgent 实例
    agent = UserProxyAgent()
    # 手动生成代理的 AgentId（此处"UserProxy"仅为示例，根据实际需求设置）
    agent_id = AgentId("UserProxy")
    # 将实例直接注册到 runtime（绕过工厂机制，不推荐）
    runtime._instantiated_agents[agent_id] = agent
    # ...其他逻辑...

asyncio.run(main())
