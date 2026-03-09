/**
 * 07 - Session Stickiness (Conversational Affinity)
 *
 * Configures session-sticky routing so that all requests within the same
 * conversation are routed to the same model. This sample demonstrates:
 *
 *   - Session-stickiness rotation policy
 *   - Sending multiple messages with the same session_id
 *   - Verifying that all messages route to the same model
 *   - Fallback behavior when the session's model becomes unavailable
 *   - Multiple independent sessions routed independently
 *
 * Session stickiness is important for multi-turn conversations where
 * switching models mid-conversation can cause inconsistency in tone,
 * context interpretation, or response style.
 *
 * Prerequisites:
 *   - Set OPENAI_API_KEY and ANTHROPIC_API_KEY environment variables
 */

import { ModelMesh, MeshConfig } from "modelmesh-lite";

async function main(): Promise<void> {
  // -----------------------------------------------------------------------
  // 1. Configure with session-stickiness policy
  // -----------------------------------------------------------------------
  const config: MeshConfig = {
    raw: {
      providers: {
        "openai.llm.v1": {
          enabled: true,
          api_key: "${secrets:OPENAI_API_KEY}",
        },
        "anthropic.llm.v1": {
          enabled: true,
          api_key: "${secrets:ANTHROPIC_API_KEY}",
        },
      },

      pools: {
        "text-generation": {
          // Session-stickiness routes all requests with the same session_id
          // to the same model. The first request in a session picks a model
          // using the fallback strategy; subsequent requests reuse it.
          strategy: "modelmesh.session-stickiness.v1",
          fallback_strategy: "modelmesh.round-robin.v1",

          deactivation: {
            retry_limit: 3,
            error_codes: [429, 500, 503],
          },
          recovery: {
            cooldown: "30s",
          },
          retry: {
            max_attempts: 2,
            backoff: "exponential_jitter",
            initial_delay: "500ms",
            retryable_codes: [429, 500, 502, 503],
            scope: "same_model",
          },
        },
      },

      observability: {
        routing: {
          connector: "modelmesh.console.v1",
        },
      },
    },
  };

  // -----------------------------------------------------------------------
  // 2. Initialize
  // -----------------------------------------------------------------------
  const mesh = new ModelMesh();
  await mesh.initialize(config);
  console.log("ModelMesh initialized with session-stickiness routing.\n");

  const client = mesh.getClient();
  const router = mesh.getRouter();

  // -----------------------------------------------------------------------
  // 3. Session A: multi-turn conversation (same session_id)
  // -----------------------------------------------------------------------
  const sessionA = "session-user-alice-001";
  console.log(`--- Session A (${sessionA}) ---\n`);

  // The RoutingOptions.sessionId is passed through the router. When using
  // the OpenAI-compatible client, the session_id can be set in metadata
  // or through the routing options on the underlying router.

  // Turn 1
  const responseA1 = await client.chat.completions.create({
    model: "text-generation",
    messages: [
      { role: "user", content: "Hi! My name is Alice. Remember it." },
    ],
    max_tokens: 100,
    // Session ID is passed as extra metadata for the routing layer
    session_id: sessionA,
  } as any);

  console.log(`Turn 1 -> Model: ${responseA1.model}`);
  console.log(`         Reply : ${(responseA1.choices[0] as any).message.content}\n`);

  // Turn 2 (should route to the SAME model)
  const responseA2 = await client.chat.completions.create({
    model: "text-generation",
    messages: [
      { role: "user", content: "Hi! My name is Alice. Remember it." },
      { role: "assistant", content: (responseA1.choices[0] as any).message.content },
      { role: "user", content: "What is my name?" },
    ],
    max_tokens: 100,
    session_id: sessionA,
  } as any);

  console.log(`Turn 2 -> Model: ${responseA2.model}`);
  console.log(`         Reply : ${(responseA2.choices[0] as any).message.content}\n`);

  // Turn 3 (should still route to the SAME model)
  const responseA3 = await client.chat.completions.create({
    model: "text-generation",
    messages: [
      { role: "user", content: "Hi! My name is Alice. Remember it." },
      { role: "assistant", content: (responseA1.choices[0] as any).message.content },
      { role: "user", content: "What is my name?" },
      { role: "assistant", content: (responseA2.choices[0] as any).message.content },
      { role: "user", content: "Tell me a joke about my name." },
    ],
    max_tokens: 150,
    session_id: sessionA,
  } as any);

  console.log(`Turn 3 -> Model: ${responseA3.model}`);
  console.log(`         Reply : ${(responseA3.choices[0] as any).message.content}\n`);

  // Verify session consistency
  const sameModel = responseA1.model === responseA2.model && responseA2.model === responseA3.model;
  console.log(`Session A consistency: ${sameModel ? "All 3 turns routed to the same model" : "Model changed mid-session (failover occurred)"}`);

  // -----------------------------------------------------------------------
  // 4. Session B: independent session (may route to a different model)
  // -----------------------------------------------------------------------
  const sessionB = "session-user-bob-002";
  console.log(`\n--- Session B (${sessionB}) ---\n`);

  const responseB1 = await client.chat.completions.create({
    model: "text-generation",
    messages: [
      { role: "user", content: "Hello, I am Bob. What provider are you?" },
    ],
    max_tokens: 100,
    session_id: sessionB,
  } as any);

  console.log(`Turn 1 -> Model: ${responseB1.model}`);
  console.log(`         Reply : ${(responseB1.choices[0] as any).message.content}\n`);

  console.log("Note: Session A and Session B may use different models,");
  console.log("demonstrating that sessions are routed independently.");
  console.log(`Session A model: ${responseA1.model}`);
  console.log(`Session B model: ${responseB1.model}`);

  // -----------------------------------------------------------------------
  // 5. Shut down
  // -----------------------------------------------------------------------
  await mesh.shutdown();
  console.log("\nModelMesh shut down.");
}

main().catch(console.error);
