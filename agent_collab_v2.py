from typing import TypedDict, List, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import csv
import time
import uuid
import tiktoken

# Initialize tokenizer
tokenizer = tiktoken.encoding_for_model("gpt-4")

def count_tokens(text: str) -> int:
    return len(tokenizer.encode(text))

# Define the state
class AgentState(TypedDict):
    messages: List[dict]
    current_agent: Literal["agent1", "agent2", "user"]
    iterations: int
    thread_id: str
    total_input_tokens: int
    total_output_tokens: int

# CSV logging function
def log_to_csv(thread_id: str, speaker: str, message: str, input_tokens: int, output_tokens: int):
    with open('conversation_log.csv', 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([
            time.strftime('%Y-%m-%d %H:%M:%S'), 
            thread_id, 
            speaker, 
            message,
            input_tokens,
            output_tokens
        ])

# Create agents with system messages
def create_agent(system_message: str, agent_name: str):
    llm = ChatOpenAI(model="gpt-4-turbo")
    
    def agent_fn(state: AgentState):
        if state["iterations"] >= MAX_ITERATIONS:
            return {
                "messages": [AIMessage(content="TERMINATE - Max iterations reached")],
                "current_agent": END,
                "iterations": state["iterations"],
                "thread_id": state["thread_id"],
                "total_input_tokens": state["total_input_tokens"],
                "total_output_tokens": state["total_output_tokens"]
            }
        
        messages = [SystemMessage(content=system_message), *state["messages"]]
        
        # Count input tokens
        input_tokens = sum(count_tokens(msg.content) for msg in messages)
        
        response = llm.invoke(messages)
        
        # Count output tokens
        output_tokens = count_tokens(response.content)
        
        log_to_csv(
            state["thread_id"], 
            agent_name, 
            response.content,
            input_tokens,
            output_tokens
        )
        
        return {
            "messages": [response],
            "current_agent": state["current_agent"],
            "iterations": state["iterations"] + 1,
            "thread_id": state["thread_id"],
            "total_input_tokens": state["total_input_tokens"] + input_tokens,
            "total_output_tokens": state["total_output_tokens"] + output_tokens
        }
    return agent_fn

def human_feedback(state: AgentState):
    user_input = interrupt("Please provide feedback (press Enter to skip):")
    
    if user_input.strip():
        input_tokens = count_tokens(user_input)
        log_to_csv(
            state["thread_id"], 
            "user", 
            user_input,
            input_tokens,
            0  # No output tokens for user input
        )
        return {
            "messages": [HumanMessage(content=user_input)],
            "current_agent": "agent1",
            "iterations": state["iterations"],
            "thread_id": state["thread_id"],
            "total_input_tokens": state["total_input_tokens"] + input_tokens,
            "total_output_tokens": state["total_output_tokens"]
        }
    
    # Print total token usage at the end
    print(f"\nTotal token usage:")
    print(f"Input tokens: {state['total_input_tokens']}")
    print(f"Output tokens: {state['total_output_tokens']}")
    print(f"Total tokens: {state['total_input_tokens'] + state['total_output_tokens']}")
    
    return {
        "messages": [], 
        "current_agent": END, 
        "iterations": state["iterations"],
        "thread_id": state["thread_id"],
        "total_input_tokens": state["total_input_tokens"],
        "total_output_tokens": state["total_output_tokens"]
    }

def route_by_response(state: AgentState):
    last_message = state["messages"][-1].content
    if "TERMINATE" in last_message.upper():
        return "interrupt"
    return "agent2" if state["current_agent"] == "agent1" else "agent1"

# Configuration
MAX_ITERATIONS = 5

# Initialize CSV log
with open('conversation_log.csv', 'w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow([
        'Timestamp', 
        'Thread ID', 
        'Speaker', 
        'Message',
        'Input Tokens',
        'Output Tokens'
    ])

# Set up agents
agent1 = create_agent(
    "You are a collaborative agent focused on problem-solving. Work with your partner to complete the task.",
    "agent1"
)
agent2 = create_agent(
    "You are a critical reviewer. Analyze and improve upon your partner's suggestions.",
    "agent2"
)

# Build graph
workflow = StateGraph(AgentState)
workflow.add_node("agent1", agent1)
workflow.add_node("agent2", agent2)
workflow.add_node("human", human_feedback)

# Set entry point
workflow.set_entry_point("agent1")

# Add edges
workflow.add_conditional_edges(
    "agent1",
    route_by_response,
    {
        "agent2": "agent2",
        "interrupt": "human"
    }
)

workflow.add_conditional_edges(
    "agent2",
    route_by_response,
    {
        "agent1": "agent1",
        "interrupt": "human"
    }
)

workflow.add_conditional_edges(
    "human",
    lambda x: "agent1" if x["messages"] else END,
    {"agent1": "agent1", END: END}
)

# Compile with checkpointer
checkpointer = MemorySaver()
app = workflow.compile(checkpointer=checkpointer)

# Example usage
thread_id = str(uuid.uuid4())
initial_state = {
    "messages": [HumanMessage(content="Let's work on this task together")],
    "current_agent": "agent1",
    "iterations": 0,
    "thread_id": thread_id,
    "total_input_tokens": 0,
    "total_output_tokens": 0
}

for output in app.stream(initial_state):
    for node, value in output.items():
        if value["current_agent"] not in [END, "human"]:
            print(f"\n--- {node.upper()} ---")
            print(value["messages"][-1].content)
