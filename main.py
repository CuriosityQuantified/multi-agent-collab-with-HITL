from typing import TypedDict, List, Dict, Union
import os
import uuid
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver
from helper_functions import save_conversation_to_csv, create_agent_prompt, AgentConfig

# Load environment variables
load_dotenv()

# Task to be completed
INITIAL_TASK = "Let's brainstorm ideas for a new mobile app that helps people learn languages. What features should we include?"

# Constants
MAX_ITERATIONS = 3  # Maximum number of single agent responses
DEBUGGING_MODE = False
MAX_ERRORS = 3  # Maximum number of consecutive errors before exiting

# Define state
class AgentState(TypedDict):
    messages: List[str]
    phase: int
    iteration: int
    csv_file: str
    agents: List[AgentConfig]  # Track agent configurations

def create_agent_node(agent_config: AgentConfig):
    """Dynamically create an agent node function."""
    def agent_node(state: AgentState) -> AgentState:
        message_history = "\n".join(state["messages"])
        prompt = create_agent_prompt(agent_config, message_history)
        
        llm = ChatOpenAI(
            temperature=agent_config["temperature"],
            model="gpt-4o-mini",
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        response = llm.invoke(prompt)
        content = response.content
        
        # Remove agent name prefix if it exists
        prefix = f"{agent_config['name']}: "
        if content.startswith(prefix):
            content = content[len(prefix):].strip()
        
        # Log conversation
        csv_file = save_conversation_to_csv(
            agent_name=agent_config["name"],
            output=content,
            input_history=message_history,
            csv_file=state.get("csv_file")
        )
        
        return {
            "messages": state["messages"] + [f"{agent_config['name']}: {content}"],
            "phase": state["phase"],
            "iteration": state["iteration"] + 1,
            "csv_file": csv_file,
            "agents": state["agents"]
        }
    
    return agent_node

def should_continue(state: AgentState) -> str:
    """Determine next agent or human feedback."""
    # If there are no messages yet, start with the first agent
    if not state["messages"]:
        return state["agents"][0]["name"]
    
    # Get current agent index and calculate next
    current_agent = state["messages"][-1].split(":")[0]
    
    # If the current message is from a human or user, start with first agent
    if current_agent in ["Human", "User Query"]:
        return state["agents"][0]["name"]
    
    # Check if we've reached max iterations BEFORE calculating next agent
    if state["iteration"] >= MAX_ITERATIONS:
        return "human"
    
    # Find current agent's index
    current_idx = next(i for i, a in enumerate(state["agents"]) if a["name"] == current_agent)
    next_idx = (current_idx + 1) % len(state["agents"])
    next_agent = state["agents"][next_idx]["name"]
    
    return next_agent

def human_feedback(state: AgentState) -> Command:
    """Get feedback from human and update state."""
    message_history = "\n".join(state["messages"])
    feedback = interrupt("Need human feedback. Review the conversation and provide guidance.")
    
    if not feedback:
        return Command(goto=END)
    
    # Return a Command that updates the state and continues to first agent
    return Command(
        update={
            "messages": state["messages"] + [f"Human: {feedback}"],
            "phase": state["phase"] + 1,
            "iteration": 0,  # Reset iteration count after feedback
            "csv_file": state["csv_file"],
            "agents": state["agents"]
        }
    )

def create_workflow(agents: List[AgentConfig]) -> StateGraph:
    """Create workflow with dynamic agents."""
    workflow = StateGraph(AgentState)
    
    # Add nodes for each agent
    for agent in agents:
        workflow.add_node(agent["name"], create_agent_node(agent))
    
    # Add human node
    workflow.add_node("human", human_feedback)
    
    # Add edges between agents
    for agent in agents:
        edges = {
            next_agent["name"]: next_agent["name"] 
            for next_agent in agents + [{"name": "human"}]
        }
        workflow.add_conditional_edges(
            agent["name"],
            should_continue,
            edges
        )
    
    # Add edge from human back to first agent
    workflow.add_edge("human", agents[0]["name"])
    
    # Set entry point
    workflow.set_entry_point(agents[0]["name"])
    
    return workflow

def main():
    """Main function to run the agent collaboration system."""
    # Get initial query
    query = INITIAL_TASK.strip()
    if not query:
        print("Query cannot be empty")
        return
    
    print(f"\n\nInitial task:\n\n{query}\n\n")
    # Example agent configurations
    agents = [
        AgentConfig(
            name="Research Agent",
            system_prompt="You are a research agent focused on gathering accurate information and providing well-researched responses.",
            temperature=0.5
        ),
        AgentConfig(
            name="Critical Agent",
            system_prompt="You are a critical agent focused on analyzing and improving responses, ensuring logical consistency and identifying potential issues.",
            temperature=0
        ),
        AgentConfig(
            name="Creative Agent",
            system_prompt="You are a creative agent focused on generating innovative and engaging responses.",
            temperature=1
        )
    ]

    # Initialize state
    initial_state: AgentState = {
        "messages": [f"User Query: {query}"],
        "phase": 1,
        "iteration": 0,
        "csv_file": None,  # Will be set by first save_conversation_to_csv call
        "agents": agents
    }
    
    # Log the initial query
    csv_file = save_conversation_to_csv(
        agent_name="User",
        output=query,
        input_history="",
        csv_file=None
    )
    initial_state["csv_file"] = csv_file
    print(f"Conversation will be logged to: {csv_file}")
    
    # Create and run workflow
    workflow = create_workflow(agents)
    
    # Initialize checkpointer and compile with debug
    thread_id = str(uuid.uuid4())
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer, debug=DEBUGGING_MODE)
    
    # Create config for the run
    config = {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": thread_id
        }
    }
    
    # Run the workflow
    state = initial_state
    error_count = 0
    last_valid_state = state  # Keep track of the last valid state
    
    while True:
        try:
            # If state is a Command, we need to stream it differently
            if isinstance(state, Command):
                stream_input = state
                state = last_valid_state  # Use last valid state for agent name lookups
            else:
                stream_input = state
                last_valid_state = state  # Update last valid state
                
            for output in app.stream(stream_input, config):
                if isinstance(output, dict):
                    if "__interrupt__" in output:
                        # This is an interrupt
                        interrupt_value = output["__interrupt__"][0].value
                        print(f"\nHuman feedback needed: {interrupt_value}")
                        feedback = input("Your feedback: ").strip()
                        if not feedback:
                            print("Ending conversation...")
                            return
                        
                        # Log the human feedback
                        message_history = "\n".join(last_valid_state["messages"])
                        csv_file = save_conversation_to_csv(
                            agent_name="Human",
                            output=feedback,
                            input_history=message_history,
                            csv_file=last_valid_state["csv_file"]
                        )
                        
                        # Create new state with the feedback
                        new_state = {
                            "messages": last_valid_state["messages"] + [f"Human: {feedback}"],
                            "phase": last_valid_state["phase"] + 1,
                            "iteration": 0,
                            "csv_file": csv_file,
                            "agents": last_valid_state["agents"]
                        }
                        
                        # Create the command with the new state
                        state = Command(resume=feedback, update=new_state)
                        break
                    else:
                        # Display agent outputs
                        for node, node_state in output.items():
                            if isinstance(last_valid_state, dict) and node in [agent["name"] for agent in last_valid_state["agents"]]:
                                print(f"\nAgent {node} output:")
                                print(f"Phase: {node_state['phase']}, Iteration: {node_state['iteration']}")
                                print(node_state["messages"][-1])
                                state = node_state
                                last_valid_state = node_state  # Update last valid state
                        error_count = 0
            else:
                break
        except Exception as e:
            print(f"An error occurred: {e}")
            error_count += 1
            if error_count >= MAX_ERRORS:
                print(f"Too many consecutive errors ({MAX_ERRORS}). Ending conversation for safety.")
                return
            print("Attempting to continue the conversation...")
            continue

if __name__ == "__main__":
    main() 