"""
05 - Interactive Chatbot Tutorial
==================================

A complete interactive chatbot you can run in your terminal.
Written for beginners who know basic Python (variables, functions,
print, for loops, while, input).

This sample demonstrates:
  - Setting up ModelMesh with one line
  - Giving the AI a personality with a system prompt
  - Building an interactive chat loop with input()
  - Keeping conversation history so the AI remembers context
  - Streaming responses so text appears word-by-word
  - Exiting gracefully when the user types "quit" or "bye"

Prerequisites:
  - Set at least one provider API key (e.g., OPENAI_API_KEY).
"""

import modelmesh

# --- Step 1: Create a client ---
# This one line sets everything up.  ModelMesh finds your API key
# automatically from environment variables.
client = modelmesh.create("chat-completion")


def main() -> None:
    # --- Step 2: Set a system prompt ---
    # The system prompt tells the AI how to behave.
    # Change this to give your bot a different personality!
    system_prompt = (
        "You are a friendly coding tutor.  Explain things simply, "
        "use analogies a teenager would understand, and keep answers short."
    )

    # --- Step 3: Start the conversation history ---
    # We store every message (yours AND the AI's) in a list so the AI
    # remembers what was said earlier in the conversation.
    messages = [{"role": "system", "content": system_prompt}]

    print("Chatbot ready!  Type your message and press Enter.")
    print("Type 'quit' or 'bye' to exit.\n")

    # --- Step 4: The chat loop ---
    while True:
        # Get input from the user.
        user_input = input("You: ")

        # Check if the user wants to leave.
        if user_input.lower() in ("quit", "bye", "exit"):
            print("Goodbye!")
            break

        # Add the user's message to the history.
        messages.append({"role": "user", "content": user_input})

        # --- Step 5: Stream the AI's response ---
        # stream=True makes the answer appear word-by-word, like typing.
        print("Bot: ", end="")
        stream = client.chat.completions.create(
            model="chat-completion",
            messages=messages,
            stream=True,
        )

        # Collect the full reply so we can save it to history.
        full_reply = ""
        for chunk in stream:
            token = chunk.choices[0].delta.content
            if token is not None:
                print(token, end="", flush=True)
                full_reply += token

        # Print a blank line after the response for readability.
        print("\n")

        # --- Step 6: Save the AI's reply to history ---
        # This lets the AI remember what it said in future turns.
        messages.append({"role": "assistant", "content": full_reply})


if __name__ == "__main__":
    main()
