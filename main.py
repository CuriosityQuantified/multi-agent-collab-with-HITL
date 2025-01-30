from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from typing import TypedDict, List, Literal

# Placeholder for your OpenAI API key
llm = ChatOpenAI(model="gpt-4-turbo")

# ========== MODIFIABLE SYSTEM MESSAGES ==========
AGENT1_SYSTEM = """You are a helpful assistant..."""  # Modify agent 1's system message
AGENT2_SYSTEM = """You are a critical reviewer..."""  # Modify agent 2's system message
# ================================================

class AgentState(TypedDict):
    messages: List[dict]
    current_agent: Literal["agent1", "agent2", "user"]

def create_agent(system_message):
    def agent_node(state: AgentState):
        messages = [
            SystemMessage(content=system_message),
            *state["messages"]
        ]
        response = llm.invoke(messages)
        return {"messages": [response], "current_agent": state["current_agent"]}
    return agent_node

def human_node(state: AgentState):
    user_input = input("User feedback (press Enter to skip): ")
    if user_input.strip():
        return {"messages": [HumanMessage(content=user_input)], "current_agent": "agent1"}
    return {"messages": [], "current_agent": END}

def route_to_agent(state: AgentState):
    last_message = state["messages"][-1].content
    if "TERMINATE" in last_message.upper():
        return "interrupt"
    return state["current_agent"]

# Set up agents
agent1 = create_agent(AGENT1_SYSTEM)
agent2 = create_agent(AGENT2_SYSTEM)

# Build graph
workflow = StateGraph(AgentState)
workflow.add_node("agent1", agent1)
workflow.add_node("agent2", agent2)
workflow.add_node("human", human_node)

# Set initial entry point
workflow.set_entry_point("agent1")

# Define edges
workflow.add_edge("agent1", "agent2")
workflow.add_edge("agent2", "check_terminate")

workflow.add_conditional_edges(
    "check_terminate",
    route_to_agent,
    {
        "interrupt": "human",
        "agent1": "agent1",
        "agent2": "agent2"
    }
)

workflow.add_conditional_edges(
    "human",
    lambda x: "agent1" if x["messages"] else END,
    {"agent1": "agent1", END: END}
)

# Compile the graph
app = workflow.compile()

# Example usage
initial_state = {
    "messages": [HumanMessage(content="Write a poem about AI collaboration")],
    "current_agent": "agent1"
}

for output in app.stream(initial_state):
    for node, value in output.items():
        if value["current_agent"] not in [END, "human"]:
            print(f"--- {node.upper()} RESPONSE ---")
            print(value["messages"][-1].content)
