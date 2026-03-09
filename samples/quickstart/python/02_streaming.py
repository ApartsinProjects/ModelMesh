"""
02 - Streaming Chat Completion
===============================

Stream a chat completion response token-by-token.  The setup is the same
as 00_hello.py; the only addition is ``stream=True`` and iterating over
the returned chunks.

This sample demonstrates:
  - Enabling streaming with the stream=True parameter
  - Iterating over response chunks
  - Accessing incremental content via chunk.choices[0].delta.content
  - Printing tokens as they arrive for a responsive user experience

Prerequisites:
  - Set at least one provider API key (e.g., OPENAI_API_KEY).
"""

import modelmesh

# Same one-liner setup as the hello-world sample.
client = modelmesh.create("chat-completion")


def main() -> None:
    print("User: Write a haiku about distributed systems.\n")
    print("Assistant: ", end="")

    # Pass stream=True to get an iterable of chunks instead of a single response.
    stream = client.chat.completions.create(
        model="chat-completion",
        messages=[
            {"role": "user", "content": "Write a haiku about distributed systems."},
        ],
        stream=True,
    )

    # Each chunk mirrors the OpenAI streaming format.
    # chunk.choices[0].delta.content holds the next piece of text (or None).
    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token is not None:
            print(token, end="", flush=True)

    # Print a final newline after the stream is complete.
    print()


if __name__ == "__main__":
    main()
