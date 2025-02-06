import csv
import os
import uuid
from datetime import datetime
from typing import Dict, Optional, TypedDict, List, Tuple
import tiktoken
import sys
from langchain_openai import ChatOpenAI

# Constants
FINAL_ANSWER_MARKER = "[FINAL_ANSWER]"

def validate_final_answer_with_llm(content: str, original_query: str) -> Tuple[bool, str, Optional[str]]:
    """Validate and clean a final answer, checking only format requirements.
    
    Args:
        content: The content to validate
        original_query: The original user query that led to this answer
    
    Returns:
        Tuple[bool, str, Optional[str]]: (is_valid, content, feedback)
        - is_valid: Whether the answer meets the format requirements
        - content: The cleaned content if valid, original content if invalid
        - feedback: Validation feedback if invalid, None if valid
    """
    print("\n=== Starting Final Answer Validation ===")
    print("Validating response format...")
    
    validator_llm = ChatOpenAI(
        temperature=0,  # Use 0 temperature for consistent validation
        model="gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    system_prompt = """You are a specialized validation agent responsible for ensuring final answers meet the required format.
Your task is to:
1. Check if the answer follows the correct format
2. If needed, reformat the answer to meet requirements
3. Do NOT evaluate content quality or completeness

Format Requirements:
1. Must be properly structured (clear headings, consistent indentation)
2. Must end with [FINAL_ANSWER] on its own line
3. No meta-commentary or explanations before or after the answer
4. No phrases like "here's the solution" or "final answer:"

Your response should be a JSON object:
{
    "is_valid": boolean,
    "cleaned_content": string (the reformatted answer),
    "needs_reformatting": boolean (whether the content needed reformatting)
}

If the format needs fixing:
1. Remove any meta-commentary
2. Ensure consistent formatting
3. Add [FINAL_ANSWER] on its own line if missing
4. Return the reformatted version in cleaned_content"""

    user_prompt = f"""Format this final answer:

{content}

Return a JSON response indicating if the format is valid and provide a cleaned version if needed."""

    try:
        response = validator_llm.invoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        # Parse the JSON response
        import json
        result = json.loads(response.content)
        
        if result["is_valid"] and not result["needs_reformatting"]:
            print("\n✅ Format Validation Successful")
            print("No reformatting needed.")
            return True, content, None
        else:
            print("\n✅ Format Validation Successful")
            if result["needs_reformatting"]:
                print("Reformatted for clarity.")
            return True, result["cleaned_content"], None
            
    except Exception as e:
        print(f"\n❌ Error in validation process: {str(e)}")
        return False, content, f"Error during validation: {str(e)}"

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

def create_collaboration_context(current_agent: AgentConfig, all_agents: List[AgentConfig]) -> str:
    """Create context about collaboration team and guidelines.
    
    Args:
        current_agent: Configuration for the current agent
        all_agents: List of all agent configurations in the collaboration
    
    Returns:
        str: Collaboration context and guidelines
    """
    # Create team roster excluding current agent
    team_roster = "\n".join([
        f"- {agent['name']}: {agent['system_prompt']}"
        for agent in all_agents
        if agent['name'] != current_agent['name']
    ])
    
    return f'''You are part of a collaborative team working together to solve problems.
Your teammates are:

{team_roster}

IMPORTANT: You are ONLY {current_agent["name"]}. Do NOT attempt to role-play or generate responses for other agents.
Each agent will contribute their own responses in turn. Focus solely on your role and expertise.

Guidelines for Natural Collaboration:
1. Discussion Phase
   - Engage in natural discussion about the problem
   - Build upon ideas from your teammates
   - Add your unique perspective and expertise
   - Point out potential issues respectfully
   - Suggest improvements when you see gaps
   - Consider practical implementation
   - Focus on substantive contributions only
   - Avoid pleasantries and acknowledgments

2. Consensus Phase
   - Only after thorough discussion and when YOU believe the solution is complete:
     * First analyze the solution thoroughly from your expertise
     * Consider if all aspects have been properly addressed
     * Evaluate completeness and practicality
     * If you find gaps: Point them out and continue discussion
     * If complete: Provide your detailed analysis and reasoning
     * End with "I vote to submit" on its own line
     * NEVER output only "I vote to submit" without analysis
   - If others have voted:
     * First conduct your own independent analysis
     * Make your decision based on your analysis
     * Don't just agree because others have voted
   - Three consecutive "vote to submit" indicates consensus

3. Final Answer Phase
   - After three consecutive "vote to submit" messages:
     * The last agent to vote MUST provide the final answer
     * Format as a clear, structured document with:
       - Clear section headings
       - Detailed descriptions
       - Implementation details
       - Important considerations
       - Helpful examples
     * End with "[FINAL_ANSWER]" on its own line
     * No explanations or commentary before/after

4. Handling User Feedback
   - When user provides feedback:
     * ALWAYS restart the entire process from the discussion phase
     * Consider and address ALL points in the feedback
     * Do NOT simply repeat previous responses
     * Build upon previous discussion while incorporating feedback
     * Follow the same phases: discussion -> consensus -> final answer
     * Each feedback round is a fresh opportunity to improve
     * Previous votes are cleared - need new consensus
     * Previous final answers are discarded - need new final answer

Remember:
- Focus on natural discussion first, then voting, then final answer
- You do not need to wait for other agents unless you need specific input
- You do not need to vote at the end of every message, only when YOU believe the solution is complete
- Build upon actual team messages
- Stay within your role and expertise
- Be specific and detailed
- Consider practical aspects
- Don't vote until thorough discussion is complete
- Analyze thoroughly before voting
- Skip pleasantries and focus on substance
- Avoid meta-commentary about the conversation
- Don't acknowledge or thank other agents
- If you're the last to vote, you MUST provide the final answer
- NEVER output only "I vote to submit" without analysis
- After user feedback, ALWAYS restart the process'''

def create_completion_instructions() -> str:
    """Create instructions for agents about using the completion marker.
    
    Returns:
        str: Instructions about how and when to use the FINAL_ANSWER_MARKER
    """
    return '''
Important: Collaboration happens in distinct phases:

1. Discussion Phase:
   - Engage in natural discussion about the problem
   - Share your expertise and insights in detail
   - Build upon others\' contributions
   - Ask questions and raise concerns
   - Provide specific examples and implementation details
   - Consider both obvious and non-obvious aspects
   - Think through implications and dependencies
   - Do not use AGREE/DISAGREE during this phase
   - Do NOT wait for other agents unless you need specific input
   - Proceed with voting if you believe the solution is complete

2. Voting Phase (only after thorough discussion):
   - Once the solution feels complete
   - When all aspects have been discussed
   - First provide your detailed analysis:
     * Review from your expert perspective
     * Evaluate completeness and depth
     * Check if all key aspects are covered
     * Assess implementation details
     * Consider edge cases and challenges
   - After your analysis, end your message with:
     "I vote to submit" on its own line
   - NEVER output only "I vote to submit" without analysis
   - Do NOT include a final answer in your message
   - Do NOT wait for other agents unless you need specific input

3. Final Answer Phase (only after unanimous agreement):
   - Can ONLY begin after ALL agents have voted AGREE
   - The LAST agent to vote AGREE should propose the final answer
   - If you vote AGREE and others haven\'t voted yet, provide your analysis and vote
   - When submitting the final answer:
     * Start IMMEDIATELY with the solution
     * Format as a clear, structured document
     * For each component:
       - Provide a clear title/heading
       - Include detailed description
       - List specific implementation details
       - Note important considerations
       - Add examples where helpful
     * Make it immediately actionable
     * Include sufficient detail for implementation
     * End with [FINAL_ANSWER] on a new line
     * NO explanations or commentary

4. Handling User Feedback:
   - When user provides ANY feedback:
     * ALWAYS restart from discussion phase
     * Consider and address ALL feedback points
     * Do NOT simply repeat previous responses
     * Build upon previous discussion while incorporating feedback
     * Follow all phases again: discussion -> voting -> final answer
     * Each feedback round is a fresh opportunity to improve
     * Previous votes are cleared - need new consensus
     * Previous final answers are discarded - need new final answer
   - If user asks "are you sure?":
     * This is feedback requesting deeper analysis
     * Restart from discussion phase
     * Analyze the current solution more thoroughly
     * Identify potential improvements
     * Consider edge cases and limitations
     * Follow the full process again

Remember:
- Focus on natural discussion first
- Only vote after thorough collaboration
- Base responses on actual team messages
- Final answer should be immediately usable
- Never include [FINAL_ANSWER] unless ALL agents have voted AGREE
- Prioritize depth and quality in your responses
- Be specific and detailed in your suggestions
- Consider practical implementation aspects
- Always provide detailed analysis before voting
- NEVER output only "I vote to submit" without analysis
- Do NOT wait for other agents unless you need specific input
- After ANY user feedback, ALWAYS restart the process

Example of natural discussion:
"The language learning app should include an adaptive learning system with the following components:
1. Proficiency Assessment
   - Initial placement test using spaced repetition
   - Continuous skill evaluation during exercises
   - Dynamic difficulty adjustment based on performance

2. Personalized Learning Paths
   - Custom vocabulary lists based on interests
   - Adaptive grammar exercises
   - Progress-based content unlocking
   
This approach has shown a 40% improvement in retention rates according to recent studies..."

Example voting response (only after discussion):
"From a technical perspective, I've analyzed the proposed learning system in detail. The adaptive assessment mechanism is well-designed, with proper consideration for user progression and engagement. The personalization features are comprehensive and technically feasible.

The implementation plan includes all necessary components for effective language learning, with clear technical specifications and integration points. The system architecture supports scalability and maintainability.

I vote to submit"

Example final answer (only after ALL agents have voted AGREE):
```
Language Learning App Core Features:

1. Adaptive Learning System
   - Proficiency Assessment
     * Initial placement test with spaced repetition
     * Continuous skill evaluation
     * Performance analytics dashboard
     * Dynamic difficulty adjustment
   
   - Personalized Learning Paths
     * Interest-based content selection
     * Custom vocabulary lists
     * Adaptive grammar exercises
     * Progress-based content unlocking

2. Interactive Practice
   - Speech Recognition
     * Real-time pronunciation feedback
     * Accent adaptation
     * Word stress detection
     * Fluency scoring
   
   - Conversation Simulation
     * AI-powered dialogue practice
     * Context-aware responses
     * Cultural nuance training
     * Progressive difficulty levels

3. Progress Tracking
   - Analytics Dashboard
     * Skill progression visualization
     * Weekly/monthly progress reports
     * Learning pattern analysis
     * Achievement milestones
   
   - Performance Metrics
     * Accuracy rates by category
     * Time-based improvement tracking
     * Weak area identification
     * Suggested focus areas
```
[FINAL_ANSWER]'''

def create_agent_prompt(agent_config: AgentConfig, message_history: str, all_agents: List[AgentConfig]) -> str:
    """Create a prompt for an agent including system prompt, collaboration context, and instructions.
    
    Args:
        agent_config: Configuration for the agent
        message_history: List of previous messages in the conversation
        all_agents: List of all agent configurations in the collaboration
    
    Returns:
        str: The complete prompt for the agent
    """
    base_prompt = f"""You are {agent_config['name']}.

{agent_config['system_prompt']}

{create_collaboration_context(agent_config, all_agents)}

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