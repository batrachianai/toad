identity = "deepagents.langchain.com"
name = "Deep Agents"
short_name = "deepagents"
url = "https://github.com/langchain-ai/deepagents"
protocol = "acp"
author_name = "LangChain"
author_url = "https://www.langchain.com/"
publisher_name = "LangChain"
publisher_url = "https://www.langchain.com/"
type = "coding"
description = "LangChain's open-source terminal coding agent built on LangGraph. File operations, shell access, sub-agents, and MCP tool support."
tags = ["open-source"]
run_command."*" = "deepagents --acp"

help = '''
# Deep Agents

LangChain's open-source terminal coding agent built on LangGraph.

Supports file operations, shell access, subagents, MCP tools, and dynamic model switching.

[deepagents-cli](https://github.com/langchain-ai/deepagents/tree/main/libs/cli)
'''

[actions."*".install]
command = "uv tool install deepagents-cli -U --python 3.12"
bootstrap_uv = true
description = "Install deepagents-cli"

[actions."*".update]
command = "uv tool install deepagents-cli -U --python 3.12"
bootstrap_uv = true
description = "Update deepagents-cli"