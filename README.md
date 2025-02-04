Below is a detailed description of the two‑agent collaboration loop built with human in the loop. The design incorporates:

-  a "phase" variable in the state to track how many cycles (i.e., how many times human feedback has been provided)  
-  looping between two agents over a set number of iterations per cycle  
-  an interrupt (human‑in‑the‑loop) mechanism using Langgraph’s interrupt function  
-  careful edge and conditional edge transitions that ensure the agents pause for human feedback before further responses

---

## Overall System Structure

The system is organized as a series of cycles. Each cycle consists of the following steps:

1. **Initialization**  
   - Create a global state that includes:  
     - a messages list that holds every message exchanged (from the initial query, through agent responses and human feedback)  
     - a phase variable initially set to 0 (representing that no human feedback has yet been provided)  
     - a constant MAX_ITERATIONS (e.g., 3) that sets how many agent message exchanges occur before waiting for human input
  
2. **Agent Collaboration Loop (Within a Cycle)**  
   - Start with the user’s initial input.  
   - For MAX_ITERATIONS iterations, alternate the responding agent:
     - **Iteration 1:**  
       - Send initial input to Agent 1.  
       - Agent 1 produces the first message.  
     - **Iteration 2:**  
       - Combine the user’s original query and Agent 1’s output, then send this full message history to Agent 2.  
       - Agent 2 produces the second message.  
     - **Iteration 3, etc.:**  
       - Continue by sending the complete message history (including previous agent messages) back to Agent 1 (or alternating if required) so it can respond.  
   - At the end of MAX_ITERATIONS, the total message history is updated with all exchanges.

3. **Human Feedback (Interrupt Stage)**  
   - Use Langgraph’s interrupt function to pause the process and trigger the human-in-the-loop. The system waits here until a human response is provided. This interrupt acts as a conditional edge:
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

## Edge & Conditional Edge Requirements

To accurately implement the workflow, you must consider the following edge and conditional requirements:

- **Edge Connections (Message Passing):**
  - Every agent’s output must be seamlessly appended to the messages state.
  - The flow of messages from one agent to the next is represented by edges that pass the full message history as input. For example, after Agent 1 produces a message, there is an edge that combines the user’s input and Agent 1’s message before being sent to Agent 2.

- **Conditional Edges (Pausing for Human Feedback):**
  - At the end of a MAX_ITERATIONS cycle, the edge that triggers human interruption must be conditional:
    - **Condition:** The cycle completes (i.e., the message count equals MAX_ITERATIONS + initial query and any previous human feedback).
    - **Action:** Invoke Langgraph’s interrupt function to pause the agent responses.
    - **Branching:**  
      - If human feedback is received, the program follows the “continue” branch—updating messages state and incrementing the phase variable.  
      - If no feedback is received, a “terminate” branch is activated, ending the system.

- **Agent Pausing:**  
  - The design ensures that neither agent produces an additional message until human feedback is received. This is implemented through a deliberate pause in the agent’s execution after a cycle of agent messages and before the next agent execution begins.

---

## Example Walkthrough

Let’s use the MAX_ITERATIONS value of 3 as an example:

1. **Cycle 1 (Phase = 0 at start):**  
   - **Iteration 1:**  
     - The system sends the initial user query to Agent 1.  
     - Agent 1 responds (Message 1).  
   - **Iteration 2:**  
     - The state now has the initial query and Message 1. This message history is sent to Agent 2.  
     - Agent 2 responds (Message 2).  
   - **Iteration 3:**  
     - The state now contains the initial query, Message 1, and Message 2. This complete history is sent again to Agent 1.  
     - Agent 1 responds (Message 3).  
   - **Human Feedback Interrupt:**  
     - Now, the system has a total of 4 messages (initial + 3 agent messages).  
     - Langgraph’s interrupt function is called, pausing the agents and waiting for user feedback.

2. **After Human Feedback:**  
   - If human feedback is provided (Message 4), it is added to the state and the phase variable is incremented to 1.  
   - The next cycle begins using the new full message history (initial query, Message 1, Message 2, Message 3, and human feedback Message 4).  
   - The agents then continue with the 3‑iteration loop as before, using the complete accumulated messages.

3. **Termination:**  
   - If at any point the human provides no feedback when prompted, the conditional edge leads to termination, and the program ends without further agent interactions.

---

## Summary of Requirements

- **State Variables:**
  - messages: List storing all queries, agent messages, and human feedback.
  - phase: Integer counter that tracks the number of completed human feedback cycles.
  - MAX_ITERATIONS: Constant defining how many agent-message exchanges occur before waiting for feedback.

- **Loop Logic:**
  1. Begin with user input.
  2. Alternate agent responses (Agent 1, then Agent 2, then Agent 1, etc.) for MAX_ITERATIONS iterations.
  3. Invoke the interrupt using Langgraph’s interrupt function to wait for human feedback.
  4. If feedback is provided, append it to state, increment the phase variable, and restart the loop with the full message history.
  5. If no feedback is provided, terminate the system.

- **Edges & Conditional Edges:**
  - Each transition from one agent to the next is represented by a state edge that carries the complete message history.
  - A conditional edge determines whether the cycle continues (human provided feedback) or terminates (no feedback).