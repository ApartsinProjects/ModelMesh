/**
 * 04 - Custom Provider Endpoint
 * ==============================
 *
 * Use QuickProvider to connect to a custom or internal API endpoint.
 * QuickProvider works with just a base_url and api_key — no ModelInfo needed.
 *
 * Prerequisites:
 *   - A running OpenAI-compatible API endpoint.
 */

import { ModelMesh, QuickProvider } from "modelmesh";

// QuickProvider: just baseUrl + apiKey, models auto-discovered
const provider = new QuickProvider({
  baseUrl: "https://my-internal-api.company.com/v1",
  apiKey: "sk-internal-key",
});

// Use via ModelMesh.create() with a config object
const client = ModelMesh.create({
  config: {
    providers: {
      internal: {
        connector: provider,
      },
    },
    pools: {
      "chat-completion": {
        capability: "chat-completion",
      },
    },
  },
});

async function main(): Promise<void> {
  const response = await client.chat.completions.create({
    model: "chat-completion",
    messages: [
      { role: "user", content: "Hello from internal API!" },
    ],
  });

  console.log(response.choices[0].message.content);
}

main();
