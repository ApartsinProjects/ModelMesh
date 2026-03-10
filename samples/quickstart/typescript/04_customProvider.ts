/**
 * 04 - Custom Provider Endpoint
 * ==============================
 *
 * Use OpenAICompatibleProvider to connect to a custom or internal API
 * endpoint.  Any OpenAI-compatible API can be integrated with just a
 * baseUrl and apiKey.
 *
 * Prerequisites:
 *   - A running OpenAI-compatible API endpoint.
 */

import {
  create,
  CompletionResponse,
  OpenAICompatibleProvider,
  createDefaultModelInfo,
} from "@modelmesh/core";

// OpenAICompatibleProvider: baseUrl + apiKey + model catalogue
const provider = new OpenAICompatibleProvider({
  baseUrl: "https://my-internal-api.company.com",
  apiKey: "sk-internal-key",
  models: [
    createDefaultModelInfo({
      id: "internal-chat",
      name: "Internal Chat Model",
      capabilities: ["generation.text-generation.chat-completion"],
    }),
  ],
  timeout: 30,
  maxRetries: 3,
  authMethod: "api_key",
  retryableCodes: [429, 500, 502, 503],
  nonRetryableCodes: [400, 401, 403],
  capabilities: ["generation.text-generation.chat-completion"],
});

// Use via create() with a config object that references the provider instance
const client = create({
  config: {
    providers: {
      internal: {
        connector: "internal.v1",
        enabled: true,
        instance: provider,
      },
    },
    models: {
      "internal-chat": {
        provider: "internal.v1",
        capabilities: ["generation.text-generation.chat-completion"],
      },
    },
    pools: {
      "chat-completion": {
        capability: "generation.text-generation.chat-completion",
      },
    },
  },
});

async function main(): Promise<void> {
  const response = (await client.chat.completions.create({
    model: "chat-completion",
    messages: [
      { role: "user", content: "Hello from internal API!" },
    ],
  })) as CompletionResponse;

  console.log(response.choices[0].message?.content);
}

main();
