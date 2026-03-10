/**
 * 05 - Interactive Chatbot Tutorial
 * ==================================
 *
 * A complete interactive chatbot you can run in your terminal.
 * Written for beginners who know basic TypeScript (variables, functions,
 * console.log, for loops, while, readline).
 *
 * This sample demonstrates:
 *   - Setting up ModelMesh with one line
 *   - Giving the AI a personality with a system prompt
 *   - Building an interactive chat loop with readline
 *   - Keeping conversation history so the AI remembers context
 *   - Streaming responses so text appears word-by-word
 *   - Exiting gracefully when the user types "quit" or "bye"
 *
 * Prerequisites:
 *   - Set at least one provider API key (e.g., OPENAI_API_KEY).
 */

import * as readline from "readline";
import { create, CompletionResponse } from "@modelmesh/core";

// --- Step 1: Create a client ---
// This one line sets everything up.  ModelMesh finds your API key
// automatically from environment variables.
const client = create("chat-completion");

interface Message {
  role: "system" | "user" | "assistant";
  content: string;
  [key: string]: unknown;
}

async function main(): Promise<void> {
  // --- Step 2: Set a system prompt ---
  // The system prompt tells the AI how to behave.
  // Change this to give your bot a different personality!
  const systemPrompt =
    "You are a friendly coding tutor.  Explain things simply, " +
    "use analogies a teenager would understand, and keep answers short.";

  // --- Step 3: Start the conversation history ---
  // We store every message (yours AND the AI's) in a list so the AI
  // remembers what was said earlier in the conversation.
  const messages: Message[] = [{ role: "system", content: systemPrompt }];

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  const ask = (prompt: string): Promise<string> =>
    new Promise((resolve) => rl.question(prompt, resolve));

  console.log("Chatbot ready!  Type your message and press Enter.");
  console.log("Type 'quit' or 'bye' to exit.\n");

  // --- Step 4: The chat loop ---
  while (true) {
    // Get input from the user.
    const userInput = await ask("You: ");

    // Check if the user wants to leave.
    if (["quit", "bye", "exit"].includes(userInput.toLowerCase())) {
      console.log("Goodbye!");
      break;
    }

    // Add the user's message to the history.
    messages.push({ role: "user", content: userInput });

    // --- Step 5: Stream the AI's response ---
    // stream: true makes the answer appear word-by-word, like typing.
    process.stdout.write("Bot: ");
    const stream = (await client.chat.completions.create({
      model: "chat-completion",
      messages,
      stream: true,
    })) as AsyncIterableIterator<CompletionResponse>;

    // Collect the full reply so we can save it to history.
    let fullReply = "";
    for await (const chunk of stream) {
      const token = chunk.choices[0].delta?.content;
      if (token != null) {
        process.stdout.write(token);
        fullReply += token;
      }
    }

    // Print a blank line after the response for readability.
    process.stdout.write("\n\n");

    // --- Step 6: Save the AI's reply to history ---
    // This lets the AI remember what it said in future turns.
    messages.push({ role: "assistant", content: fullReply });
  }

  rl.close();
}

main();
