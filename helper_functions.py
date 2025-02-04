import csv
import os
import uuid
from datetime import datetime
from typing import Dict, Optional
import tiktoken
import sys

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