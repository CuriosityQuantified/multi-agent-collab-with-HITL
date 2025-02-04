import csv
import os
import uuid
from datetime import datetime
from typing import Dict, Optional, TypedDict, List
import tiktoken
import sys

class AgentConfig(TypedDict):
    name: str
    system_prompt: str
    temperature: float

def create_agent(name: str, system_prompt: str, temperature: float = 0.7) -> AgentConfig:
    """Create an agent configuration.
    
    Args:
        name: Name of the agent
        system_prompt: The system prompt defining the agent's role and behavior
        temperature: Temperature setting for the LLM (default: 0.7)
    
    Returns:
        AgentConfig: Configuration for the agent
    """
    return AgentConfig(
        name=name,
        system_prompt=system_prompt,
        temperature=temperature
    )

def create_agent_prompt(agent_config: AgentConfig, message_history: List[str]) -> str:
    """Create a prompt for an agent including system prompt and collaboration instructions.
    
    Args:
        agent_config: Configuration for the agent
        message_history: List of previous messages in the conversation
    
    Returns:
        str: The complete prompt for the agent
    """
    base_prompt = f"""You are {agent_config['name']}.

{agent_config['system_prompt']}

You are collaborating with other agents to respond to user queries. Your role is to:
1. Build upon previous responses
2. Critically evaluate other agents' responses
3. Provide high-quality, accurate information
4. Stay focused on the user's original query

Previous conversation:
{message_history}"""
    
    return base_prompt

def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count the number of tokens in a text string."""
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception:
        # Fallback to approximate token count if tiktoken fails
        return len(text.split()) * 1.3

def save_conversation_to_csv(
    agent_name: str,
    output: str,
    input_history: str,
    csv_file: Optional[str] = None
) -> str:
    """
    Save a conversation entry to a CSV file.
    
    Args:
        agent_name: Name of the agent (e.g., "Agent 1", "Agent 2", "Human")
        output: The agent's response
        input_history: The input history provided to the agent
        csv_file: Optional path to existing CSV file. If None, creates new file.
    
    Returns:
        str: Path to the CSV file
    """
    try:
        # Create the CSV filename if not provided
        if csv_file is None:
            timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
            unique_id = str(uuid.uuid4())[:8]
            csv_file = f"{timestamp}_conversation_log_{unique_id}.csv"
            
            # Ensure the directory exists
            os.makedirs("conversation_logs", exist_ok=True)
            csv_file = os.path.join("conversation_logs", csv_file)
        
        # Calculate token counts
        input_tokens = count_tokens(input_history)
        output_tokens = count_tokens(output)
        
        # Prepare the row data
        row_data = {
            "agent_name": agent_name,
            "output": output,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Add timestamp for each entry
        }
        
        # Write to CSV
        file_exists = os.path.exists(csv_file)
        with open(csv_file, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=row_data.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(row_data)
            f.flush()  # Ensure immediate write to disk
            os.fsync(f.fileno())  # Force the operating system to write to disk
        
        return csv_file
    
    except Exception as e:
        print(f"Error saving conversation to CSV: {e}", file=sys.stderr)
        raise  # Re-raise the exception after logging 