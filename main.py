from typing import TypedDict, List, Dict, Union, Tuple, Optional
import os
import uuid
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver
from helper_functions import (
    save_conversation_to_csv, 
    create_agent_prompt, 
    AgentConfig,
    FINAL_ANSWER_MARKER,
    validate_final_answer_with_llm
)

# Load environment variables
load_dotenv()

# Task to be completed
INITIAL_TASK = "Let's brainstorm ideas for a new mobile app that helps people learn languages. What features should we include?"

# Constants
MAX_ITERATIONS = 20  # Increased to allow for more iterations before safety cutoff
DEBUGGING_MODE = False
MAX_ERRORS = 3  # Maximum number of consecutive errors before exiting

# Define state
class AgentState(TypedDict):
    messages: List[str]
    phase: int
    iteration: int
    csv_file: str
    agents: List[AgentConfig]  # Track agent configurations

def validate_message(content: str, agent_name: str, all_agent_names: List[str], original_query: str, messages: List[str]) -> Tuple[str, Optional[str]]:
    """Validate that the message follows proper format and doesn't contain role-playing.
    
    Args:
        content: The message content to validate
        agent_name: The name of the current agent
        all_agent_names: List of all agent names
        original_query: The original user query
        messages: List of all previous messages
    
    Returns:
        Tuple[str, Optional[str]]: (validated_content, validation_feedback)
    """
    # Remove the current agent from the list to check
    other_agents = [name for name in all_agent_names if name != agent_name]
    
    # Check for and remove role-playing attempts
    for other_agent in other_agents:
        if f"{other_agent}:" in content:
            content = content.split(f"{other_agent}:")[0].strip()
    
    # Check for other common role-playing indicators
    indicators = ["**" + name + ":**" for name in other_agents]
    for indicator in indicators:
        if indicator in content:
            content = content.split(indicator)[0].strip()
    
    # Get the last three non-feedback messages
    vote_messages = []
    for msg in reversed(messages):
        if not msg.startswith("Validation Feedback:") and not msg.startswith("Human:") and not msg.startswith("User Query:"):
            vote_messages.append(msg)
            if len(vote_messages) == 3:
                break
    
    # Check if this is a final answer
    if FINAL_ANSWER_MARKER in content:
        # Check if we have three consecutive "vote to submit" messages
        if len(vote_messages) == 3 and all("i vote to submit" in msg.lower() for msg in vote_messages):
            # Print the final answer before validation
            print("\nFinal Answer:")
            print(content)
            print("\nValidating final answer format...")
            
            # Validate the final answer format
            is_valid, validated_content, validation_feedback = validate_final_answer_with_llm(content, original_query)
            if is_valid:
                return validated_content, None
            else:
                return content, f"Final answer format needs improvement: {validation_feedback}"
        else:
            return content.replace(FINAL_ANSWER_MARKER, "").strip(), "Final answer can only be provided after three consecutive agents have voted to submit"
    
    # Check for consensus building
    if "i vote to submit" in content.lower():
        # Check if this is too early (not enough discussion)
        if len(messages) < 3 and not any("i vote to submit" in msg.lower() for msg in messages):
            return content, "Please engage in thorough discussion before voting to submit"
        
        # If we have three consecutive "vote to submit" messages, remind the last agent to provide final answer
        if len(vote_messages) == 3 and all("i vote to submit" in msg.lower() for msg in vote_messages):
            return content, "Consensus reached! As the last agent to vote, please provide the final answer following the format guidelines."
    
    return content, None

def create_agent_node(agent_config: AgentConfig):
    """Dynamically create an agent node function."""
    def agent_node(state: AgentState) -> AgentState:
        message_history = "\n".join(state["messages"])
        
        # Get the original query from the first message
        original_query = state["messages"][0].split(":", 1)[1].strip()
        
        # Check if there's validation feedback in the last message
        validation_feedback = None
        if state["messages"] and state["messages"][-1].startswith("Validation Feedback:"):
            validation_feedback = state["messages"][-1].split(":", 1)[1].strip()
            # Remove the validation feedback from message history
            message_history = "\n".join(state["messages"][:-1])
        
        # Add validation feedback to prompt if it exists
        if validation_feedback:
            message_history += f"\n\nPlease address the following validation issues:\n{validation_feedback}"
        
        prompt = create_agent_prompt(
            agent_config=agent_config,
            message_history=message_history,
            all_agents=state["agents"]
        )
        
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
        
        # Validate message with original query
        all_agent_names = [agent["name"] for agent in state["agents"]]
        content, feedback = validate_message(content, agent_config["name"], all_agent_names, original_query, state["messages"])
        
        # If there's validation feedback, add it as a separate message
        messages = state["messages"]
        if feedback:
            messages = messages + [f"Validation Feedback: {feedback}"]
            # Reset iteration to allow the agent to try again
            return {
                "messages": messages,
                "phase": state["phase"],
                "iteration": state["iteration"],  # Don't increment iteration for validation feedback
                "csv_file": state["csv_file"],
                "agents": state["agents"]
            }
        
        # Log conversation
        csv_file = save_conversation_to_csv(
            agent_name=agent_config["name"],
            output=content,
            input_history=message_history,
            csv_file=state.get("csv_file")
        )
        
        return {
            "messages": messages + [f"{agent_config['name']}: {content}"],
            "phase": state["phase"],
            "iteration": state["iteration"] + 1,
            "csv_file": csv_file,
            "agents": state["agents"]
        }
    
    return agent_node

def should_continue(state: AgentState) -> str:
    """Determine next agent or human feedback.
    
    Returns the name of the next agent or "human" for feedback.
    """
    # If there are no messages yet, start with the first agent
    if not state["messages"]:
        return state["agents"][0]["name"]
    
    # Get current agent index and calculate next
    current_agent = state["messages"][-1].split(":")[0]
    last_message = state["messages"][-1]
    
    # If the current message is from a human or user, start with first agent
    if current_agent in ["Human", "User Query"]:
        return state["agents"][0]["name"]
    
    # Check if we've reached max iterations
    if state["iteration"] >= MAX_ITERATIONS:
        return "human"
    
    # Check if final answer was provided
    if FINAL_ANSWER_MARKER in last_message:
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
    
    try:
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
            except StopIteration:
                # This is expected when the workflow ends normally
                break
            except Exception as e:
                print(f"An error occurred: {e}")
                error_count += 1
                if error_count >= MAX_ERRORS:
                    print(f"Too many consecutive errors ({MAX_ERRORS}). Ending conversation for safety.")
                    return
                print("Attempting to continue the conversation...")
                continue
    except KeyboardInterrupt:
        print("\nConversation interrupted by user.")
    finally:
        print("\nConversation ended.")
        if state.get("csv_file"):
            print(f"Conversation log saved to: {state['csv_file']}")

if __name__ == "__main__":
    main() 