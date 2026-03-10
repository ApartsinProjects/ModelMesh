/**
 * 10 - LangChain Integration
 *
 * Shows how to use ModelMesh Lite as the transport layer for LangChain.
 * The OpenAI-compatible client from ModelMesh is passed to LangChain's
 * ChatOpenAI class, enabling all LangChain features (chains, agents,
 * retrieval) while ModelMesh handles routing, failover, and quota
 * management transparently. This sample demonstrates:
 *
 *   - Creating an OpenAI client from ModelMesh
 *   - Passing it to LangChain's ChatOpenAI constructor
 *   - Running a simple LangChain prompt chain
 *   - Running a multi-step chain (prompt -> LLM -> output parser)
 *   - Verifying that routing, failover, and quota management happen
 *     transparently beneath LangChain
 *
 * ModelMesh Lite does not replace LangChain -- it operates one layer below,
 * providing reliable, cost-optimized access to the AI provider APIs that
 * LangChain depends on.
 *
 * Prerequisites:
 *   - npm install langchain @langchain/openai @langchain/core
 *   - Set OPENAI_API_KEY and ANTHROPIC_API_KEY environment variables
 *
 * NOTE: This sample requires @langchain/openai and @langchain/core to be
 * installed separately. It will not compile without those packages.
 */

// @ts-nocheck -- LangChain dependencies are optional; skip type checking
import { ModelMesh, MeshConfig } from "@nistrapa/modelmesh-core";
import { ChatOpenAI } from "@langchain/openai";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";

async function main(): Promise<void> {
  // -----------------------------------------------------------------------
  // 1. Configure ModelMesh with multiple providers
  // -----------------------------------------------------------------------
  const config = new MeshConfig({
    providers: {
      "openai.llm.v1": {
        enabled: true,
        api_key: "${secrets:OPENAI_API_KEY}",
        budget: {
          daily_limit: 5.00,
        },
      },
      "anthropic.claude.v1": {
        enabled: true,
        api_key: "${secrets:ANTHROPIC_API_KEY}",
        budget: {
          daily_limit: 5.00,
        },
      },
    },

    pools: {
      "text-generation": {
        strategy: "modelmesh.cost-first.v1",
        deactivation: {
          retry_limit: 3,
          error_codes: [429, 500, 503],
        },
        recovery: {
          cooldown: "60s",
          on_quota_reset: true,
        },
        retry: {
          max_attempts: 2,
          backoff: "exponential_jitter",
          initial_delay: "500ms",
          retryable_codes: [429, 500, 502, 503],
          scope: "same_provider",
        },
      },
    },

    observability: {
      routing: {
        connector: "modelmesh.console.v1",
      },
    },
  });

  // -----------------------------------------------------------------------
  // 2. Initialize ModelMesh
  // -----------------------------------------------------------------------
  const mesh = new ModelMesh();
  mesh.initialize(config);
  console.log("ModelMesh initialized.\n");

  // -----------------------------------------------------------------------
  // 3. Create a LangChain ChatOpenAI using the ModelMesh client
  // -----------------------------------------------------------------------
  const meshClient = mesh.getClient();

  const llm = new ChatOpenAI({
    client: meshClient as any,
    modelName: "text-generation",
    temperature: 0.7,
    maxTokens: 200,
  });

  console.log("LangChain ChatOpenAI created with ModelMesh backend.\n");

  // -----------------------------------------------------------------------
  // 4. Simple prompt chain
  // -----------------------------------------------------------------------
  console.log("--- Simple Chain ---\n");

  const simplePrompt = ChatPromptTemplate.fromMessages([
    ["system", "You are a helpful assistant that explains concepts simply."],
    ["human", "{question}"],
  ]);

  const simpleChain = simplePrompt.pipe(llm).pipe(new StringOutputParser());

  const simpleResult = await simpleChain.invoke({
    question: "What is a neural network?",
  });

  console.log(`Question: What is a neural network?`);
  console.log(`Answer  : ${simpleResult}\n`);

  // -----------------------------------------------------------------------
  // 5. Multi-step chain (translation pipeline)
  // -----------------------------------------------------------------------
  console.log("--- Translation Chain ---\n");

  const translatePrompt = ChatPromptTemplate.fromMessages([
    ["system", "You are a professional translator. Translate the following text to {language}. Return only the translation."],
    ["human", "{text}"],
  ]);

  const translateChain = translatePrompt.pipe(llm).pipe(new StringOutputParser());

  const translations = [
    { text: "Hello, how are you today?", language: "French" },
    { text: "The weather is beautiful.", language: "Japanese" },
    { text: "Programming is fun.", language: "Spanish" },
  ];

  for (const { text, language } of translations) {
    const translated = await translateChain.invoke({ text, language });
    console.log(`"${text}" -> [${language}] "${translated}"`);
  }

  // -----------------------------------------------------------------------
  // 6. Chain with structured output parsing
  // -----------------------------------------------------------------------
  console.log("\n--- Structured Analysis Chain ---\n");

  const analysisPrompt = ChatPromptTemplate.fromMessages([
    [
      "system",
      "You are a text analyst. Analyze the sentiment of the given text. " +
      "Respond with exactly: POSITIVE, NEGATIVE, or NEUTRAL followed by " +
      "a one-sentence explanation.",
    ],
    ["human", "{text}"],
  ]);

  const analysisChain = analysisPrompt.pipe(llm).pipe(new StringOutputParser());

  const texts = [
    "I absolutely love this new feature! It works perfectly.",
    "The service was terrible and the food was cold.",
    "The meeting is scheduled for 3 PM tomorrow.",
  ];

  for (const text of texts) {
    const analysis = await analysisChain.invoke({ text });
    console.log(`Text    : "${text}"`);
    console.log(`Analysis: ${analysis}\n`);
  }

  // -----------------------------------------------------------------------
  // 7. Demonstrate transparent failover
  // -----------------------------------------------------------------------
  console.log("--- Transparent Failover ---\n");
  console.log("LangChain is unaware of the underlying provider routing.");
  console.log("If OpenAI is unavailable, ModelMesh automatically routes to");
  console.log("Anthropic. The LangChain chain continues without errors.\n");

  const failoverResult = await simpleChain.invoke({
    question: "Explain the concept of failover in distributed systems.",
  });

  console.log(`Answer: ${failoverResult}\n`);

  // -----------------------------------------------------------------------
  // 8. Shut down
  // -----------------------------------------------------------------------
  mesh.shutdown();
  console.log("ModelMesh shut down.");
  console.log("\nNote: All LangChain calls above were routed through ModelMesh.");
  console.log("Check the console output above for [routing] log lines showing");
  console.log("which real model and provider served each request.");
}

main().catch(console.error);
