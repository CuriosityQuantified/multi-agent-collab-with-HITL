from typing import TypedDict, List, Dict, Union
import os
import uuid
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver

# Load environment variables
load_dotenv()

# Initialize LLM
llm = ChatOpenAI(
    temperature=0.7,
    model="gpt-4o-mini",
    api_key=os.getenv("OPENAI_API_KEY")
)

# Constants
MAX_ITERATIONS = 2  # Maximum number of single agent responses

# Define state
class AgentState(TypedDict):
    messages: List[str]
    phase: int
    iteration: int

def create_agent_prompt(agent_id: int) -> ChatPromptTemplate:
    """Create a prompt template for the specified agent."""
    template = """You are Agent {agent_id}. Previous conversation:
{message_history}

Important: Only respond to the actual conversation. DO NOT make up or hallucinate any user queries.
Provide your response, building upon previous messages."""
    
    return ChatPromptTemplate.from_template(template)

def agent1(state: AgentState) -> AgentState:
    """Agent 1's response function."""
    prompt = create_agent_prompt(1)
    response = llm.invoke(
        prompt.format_messages(
            agent_id=1,
            message_history="\n".join(state["messages"])
        )
    )
    
    # Remove "Agent 1:" prefix if it exists in the response
    content = response.content
    if content.startswith("Agent 1:"):
        content = content[len("Agent 1:"):].strip()
    
    return {
        "messages": state["messages"] + [f"Agent 1: {content}"],
        "phase": state["phase"],
        "iteration": state["iteration"] + 1
    }

def agent2(state: AgentState) -> AgentState:
    """Agent 2's response function."""
    prompt = create_agent_prompt(2)
    response = llm.invoke(
        prompt.format_messages(
            agent_id=2,
            message_history="\n".join(state["messages"])
        )
    )
    
    # Remove "Agent 2:" prefix if it exists in the response
    content = response.content
    if content.startswith("Agent 2:"):
        content = content[len("Agent 2:"):].strip()
    
    return {
        "messages": state["messages"] + [f"Agent 2: {content}"],
        "phase": state["phase"],
        "iteration": state["iteration"] + 1
    }

def should_continue(state: AgentState) -> str:
    """Determine if we should continue to the next agent or get human feedback."""
    if state["iteration"] >= MAX_ITERATIONS:
        return "human"
    # Route to the opposite agent of the last message
    last_message = state["messages"][-1]
    if last_message.startswith("Agent 1:"):
        return "agent2"
    return "agent1"

def human_feedback(state: AgentState) -> Command:
    """Get feedback from human and update state."""
    feedback = interrupt("Need human feedback. Review the conversation and provide guidance.")
    
    if not feedback:
        return Command(goto=END)
    
    # Return a Command that updates the state and continues to agent1
    return Command(
        update={
            "messages": state["messages"] + [f"Human: {feedback}"],
            "phase": state["phase"] + 1,
            "iteration": 0
        }
    )

def create_workflow() -> StateGraph:
    """Create the workflow graph."""
    # Create graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("agent1", agent1)
    workflow.add_node("agent2", agent2)
    workflow.add_node("human", human_feedback)
    
    # Add conditional edges for routing between agents and human feedback
    workflow.add_conditional_edges(
        "agent1",
        should_continue,
        {
            "agent2": "agent2",
            "human": "human"
        }
    )
    
    workflow.add_conditional_edges(
        "agent2",
        should_continue,
        {
            "agent1": "agent1",
            "human": "human"
        }
    )
    
    # Add edge from human back to agent1
    workflow.add_edge("human", "agent1")
    
    # Set entry point
    workflow.set_entry_point("agent1")
    
    return workflow

def main():
    """Main function to run the agent collaboration system."""
    # Get initial query
    query = input("Enter your query: ").strip()
    if not query:
        print("Query cannot be empty")
        return

    # Initialize state
    initial_state: AgentState = {
        "messages": [f"User Query: {query}"],
        "phase": 1,
        "iteration": 0
    }
    
    # Create and run workflow
    workflow = create_workflow()
    
    # Initialize checkpointer
    thread_id = str(uuid.uuid4())
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    
    # Create config for the run
    config = {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": thread_id
        }
    }
    
    # Run the workflow
    state = initial_state
    while True:
        try:
            for output in app.stream(state, config):
                if isinstance(output, dict):
                    if "__interrupt__" in output:
                        # This is an interrupt
                        interrupt_value = output["__interrupt__"][0].value
                        print(f"\nHuman feedback needed: {interrupt_value}")
                        feedback = input("Your feedback: ").strip()
                        if not feedback:
                            print("Ending conversation...")
                            return
                        
                        # Create new state with the feedback
                        state = {
                            "messages": state["messages"] + [f"Human: {feedback}"],
                            "phase": state["phase"] + 1,
                            "iteration": 0
                        }
                        # Resume the workflow with the feedback
                        state = Command(resume=feedback, update=state)
                        break  # Break the inner loop to restart with new input
                    else:
                        # Display agent outputs
                        for node, node_state in output.items():
                            if node in ["agent1", "agent2"]:
                                print(f"\nAgent {node} output:")
                                print(f"Phase: {node_state['phase']}, Iteration: {node_state['iteration']}")
                                print(node_state["messages"][-1])
                                # Update our state tracking
                                state = node_state
            else:
                # If we complete the loop without breaking, we're done
                break
        except Exception as e:
            print(f"An error occurred: {e}")
            break

if __name__ == "__main__":
    main() 