# PoC for samples/no_risk_levels_agent.py — unmodified.
# Needs: pip install langchain langchain-openai
#        export OPENAI_API_KEY=sk-...
# Run in a disposable VM/container — gpt-4o will really call execute_shell
# and delete_file with whatever arguments it decides on.

"""LangChain agent that executes tools without risk assessment."""
from langchain_openai import ChatOpenAI
from langchain.tools import tool

@tool
def execute_shell(command: str) -> str:
    """Execute a shell command and return output."""
    import subprocess
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout

@tool
def delete_file(path: str) -> str:
    """Delete a file from the filesystem."""
    import os
    os.remove(path)
    return f"Deleted {path}"

llm = ChatOpenAI(model="gpt-4o")

# No risk classification — any tool can be called freely
from langchain.agents import AgentExecutor, create_openai_tools_agent
tools = [execute_shell, delete_file]
agent = create_openai_tools_agent(llm, tools, prompt=None)
executor = AgentExecutor(agent=agent, tools=tools)
result = executor.invoke({"input": "List all files in /etc and delete temp files"})
print(result)
