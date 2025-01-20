## AgentChat: The core concept of task-driven applications

1. Models

The agent needs to accessLLM the model service.Since there are many different providers with different APIs, autogen-core implements a protocol for model clients.
autogen-ext, on the other hand, implements a set of model clients for popular model services, such as OpenAI and local models.

2. Messages

In AgentChat, messages facilitate communication and information exchange with other agents, orchestrators, and applications.

AgentChat supports a variety of message types, each designed for a specific purpose.

1) Agent-Agent Messages

This message type allows text and multimodal communication and contains other message types such as TextMessage or MultiModalMessage.

2) Internal Events

These messages are used to convey information about events and operations within the agent itself.

3. Agents

AgentChat provides a set of preset Agents, each of which is different in the way it responds to messages:

    A. AssistantAgent: is a built-in agent that uses large language models and has the ability to use tools
    B. UserProxyAgent: The agent that accepts the user's input returns it as a response
    C. CodeExecutorAgent: an agent that can execute code
    D. OpenAIAssistantAgent: An agent powered by OpenAI Assistant with the ability to use custom tools
    E. MultimodalWebSurfer: A multimodal agent that can search the web and visit web pages for information
    F. FileSurfer: An agent that can search and browse local files for information
    G. VideoSurfer: An agent that can watch videos to obtain information

All agents share the following properties and methods:

    properties:

    A. name:  Specify the unique name of the agent
    B. description: Description of the agent
    C. model_client: Specifies the large language model to be used by the agent

    methods:

    A. on_messages(): 向Agent发送一系列ChatMessage并获取Response
    B. on_messages_stream(): 与on_messages()相同，但返回AgentEvent或ChatMessage的迭代器，后跟Response作为最后一项
    C. on_reset(): Reset the agent to its initial state
    D. run() and run_stream(): A convenient way to call on_messages() and on_messages_stream() separately, but provide the same interface as Teams

AssistantAgent: a built-in Agent with additional properties associated with it.

    tools： A collection of tools provided to the agent
    system_message: The system prompt of the agent
    model_context： Use model contexts

4. Teams

In AgentChat, a team consists of one or more agents and defines how the agent group works together to complete tasks.
Team is stateful and maintains context across multiple tasks, requiring termination conditions to decide when to stop working on the current task.

AgentChat provides a set of presets for Teams:

A. BaseGroupChat: Team's base class, and the other 4 Team preset categories inherit this base class
B. RoundRobinGroupChat: The participants in the preset team release information to all participants in a sequential loop.The preset Team allows all agents to share context and respond in a circular fashion

    Its properties are as follows:
        
        participants: Set the Agent and List of the team

        termination_condition: The Team terminates the condition, and the default None runs indefinitely

        max_turns: The maximum number of session rounds supported by Team, and the default None is unlimited

c.SelectorGroupChat: Agents in the preset team take turns to release information to all participants in a recommended manner.After each message, the next Agent is selected using ChatCompletionClient(LLM)

    Its properties are as follows:

        participants: Set the Agent and List of the team

        termination_condition: The Team terminates the condition, and the default None runs indefinitely

        max_turns: The maximum number of session rounds supported by Team, and the default None is unlimited

        selector_prompt: The prompt template used to select the next speaker

        allow_repeated_speaker: Whether to allow the same speaker to be selected consecutively, but not to allow the default False setting

        selector_func: A custom selector function to get the conversation history and return the next Agent, if the function is enabled, theLLM selection will be invalid, and if the function returns None, then LLM will take over the selection of the next Agent.

    