"""ModelMesh starter project — Python."""

import modelmesh


def main():
    # Create a client with chat completion capability
    client = modelmesh.create("chat-completion")

    # Show available providers
    print(client.describe())
    print()

    # Send a request
    response = client.chat.completions.create(
        model="chat-completion",
        messages=[{"role": "user", "content": "Hello! What can you help me with?"}],
    )
    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
