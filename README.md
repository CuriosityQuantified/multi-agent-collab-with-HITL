Below is a detailed description of the multi-agent collaboration loop built with human in the loop. The design incorporates:

-  a "phase" variable in the state to track how many cycles (i.e., how many times human feedback has been provided)  
-  looping between multiple agents over a set number of iterations per cycle  
-  an interrupt (human‑in‑the‑loop) mechanism using Langgraph's interrupt function  
-  agents pausing for human feedback before further responses

---

## Overall System Structure

The system is organized as a series of cycles. Each cycle consists of the following steps:

1. **Initialization**  
   - Create a global state that includes:  
     - a messages list that holds every message exchanged (from the initial query, through agent responses and human feedback)  
     - a phase variable initially set to 1 (representing that no human feedback has yet been provided)  
     - a constant MAX_ITERATIONS (e.g., 3) that sets how many agent message exchanges occur before waiting for human input
  
2. **Agent Collaboration Loop (Within a Cycle)**  
   - Start with the user's initial input.  
   - For MAX_ITERATIONS iterations, alternate the responding agent:
     - **Iteration 1:**  
       - Send initial input to the first agent.  
       - The agent produces the first message.  
     - **Iteration 2:**  
       - Combine the user's original query and the first agent's output, then send this full message history to the next agent.  
       - The next agent produces the second message.  
     - **Iteration 3, etc.:**  
       - Continue by sending the complete message history (including previous agent messages) back to the next agent (or alternating if required) so it can respond.  
   - At the end of MAX_ITERATIONS, the total message history is updated with all exchanges.

3. **Human Feedback (Interrupt Stage)**  
   - Use Langgraph's interrupt function to pause the process and trigger the human-in-the-loop. The system waits here until a human response is provided. This interrupt acts as a conditional edge:
     - **If human feedback is provided:**  
       - Append the human feedback to the message history.  
       - Increment the phase variable by one (tracking how many cycles have received feedback).  
     - **If no human feedback is given:**  
       - End the program immediately.  

4. **Next Cycle**  
   - With human feedback integrated, the agent collaboration loop is restarted using the complete message history.  
   - The cycle will follow the same MAX_ITERATIONS steps, now starting a new phase (as tracked by the incremented phase variable).  
   - This loop continues until the human does not provide any feedback during an interrupt, at which point the system terminates.

---

## Updated Features

This project implements a dynamic multi-agent collaboration system with human-in-the-loop feedback. Key features include:

- **Dynamic Agent Creation**: Agents are created dynamically with specific configurations, including name, system prompt, and temperature settings. This allows for flexible and scalable agent management.

- **Enhanced Collaboration**: Agents collaborate by building upon previous responses, critically evaluating each other's outputs, and providing creative solutions. This ensures high-quality and diverse responses.

- **Human Feedback Integration**: The system pauses for human feedback at specified intervals, allowing users to guide the conversation and provide additional context or corrections.

- **Error Handling and Logging**: Comprehensive error handling and logging have been implemented to improve debugging and user experience.

- **Environment Configuration**: The system uses environment variables for configuration, including API keys for accessing language models.

## Usage Instructions

To run the program, follow these steps:

1. **Clone the Repository**: Ensure you have cloned the repository, including submodules.

2. **Set Up Environment**: Create a `.env` file with the necessary environment variables, such as `OPENAI_API_KEY`.

3. **Install Dependencies**: Use a virtual environment and install the required packages.

4. **Run the Program**: Execute the `main.py` script to start the agent collaboration system.

5. **Provide Feedback**: During execution, provide feedback when prompted to guide the conversation.

## Example Walkthrough

The system operates in cycles, with each cycle consisting of agent interactions and human feedback. The process continues until no further feedback is provided, at which point the system terminates.

For more detailed information, refer to the sections above describing the system structure and example walkthrough.
