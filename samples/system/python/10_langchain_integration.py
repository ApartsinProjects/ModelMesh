"""
10 - LangChain Integration
===========================

Using ModelMesh Lite as the backend for LangChain.  The ModelMesh OpenAI
client is passed to LangChain's ChatOpenAI, so all routing, failover, quota
management, and cost optimization happen transparently underneath LangChain's
abstractions.

This sample demonstrates:
  - Creating an OpenAI-compatible client from ModelMesh
  - Passing the client to LangChain's ChatOpenAI
  - Running a simple LangChain chain (prompt template + LLM + output parser)
  - Showing that routing and failover are fully transparent to LangChain

Prerequisites:
  - pip install langchain langchain-openai
  - Set OPENAI_API_KEY and ANTHROPIC_API_KEY environment variables.

How it works:
  LangChain's ChatOpenAI accepts a custom `http_client` or can connect to an
  OpenAI-compatible base URL.  ModelMesh exposes an OpenAI-compatible
  interface, so LangChain does not need to know about multiple providers,
  rotation policies, or failover logic.  It simply makes standard OpenAI SDK
  calls, and ModelMesh handles the rest.
"""

import asyncio
import yaml
from modelmesh import ModelMesh, MeshConfig

CONFIG_YAML = """
secrets:
  store: modelmesh.env.v1

providers:
  openai.llm.v1:
    enabled: true
    api_key: ${secrets:OPENAI_API_KEY}
    budget:
      daily_limit: 5.00

  anthropic.llm.v1:
    enabled: true
    api_key: ${secrets:ANTHROPIC_API_KEY}
    budget:
      daily_limit: 5.00

models:
  gpt-4o-mini:
    provider: openai.llm.v1
    capabilities:
      - generation.text-generation.chat-completion
      - generation.structured-generation.json-generation
    delivery:
      synchronous: true
      streaming: true
    features:
      tool_calling: true
      structured_output: true
      system_prompt: true
    constraints:
      context_window: 128000
      max_output_tokens: 16384

  claude-sonnet-4:
    provider: anthropic.llm.v1
    capabilities:
      - generation.text-generation.chat-completion
    delivery:
      synchronous: true
      streaming: true
    features:
      tool_calling: true
      system_prompt: true
    constraints:
      context_window: 200000
      max_output_tokens: 16384

pools:
  text-generation:
    strategy: modelmesh.cost-first.v1
    deactivation:
      retry_limit: 3
      error_codes: [429, 500, 503]
    recovery:
      cooldown: 30s
    retry:
      max_attempts: 2
      backoff: exponential_jitter
      initial_delay: 500ms
      scope: any

observability:
  routing:
    connector: modelmesh.console.v1
"""


async def main() -> None:
    # -----------------------------------------------------------------------
    # 1. Initialize ModelMesh
    # -----------------------------------------------------------------------
    config = MeshConfig(raw=yaml.safe_load(CONFIG_YAML))
    mesh = ModelMesh()
    mesh.initialize(config)

    # Get the OpenAI-compatible client from ModelMesh.
    modelmesh_client = mesh.get_client()

    print("=" * 60)
    print("LangChain + ModelMesh integration demo")
    print("=" * 60)
    print()
    print("ModelMesh provides an OpenAI-compatible client that LangChain")
    print("uses transparently.  Routing, failover, and quota management")
    print("happen below LangChain's abstraction layer.\n")

    # -----------------------------------------------------------------------
    # 2. Create a LangChain ChatOpenAI instance backed by ModelMesh
    # -----------------------------------------------------------------------
    # LangChain's ChatOpenAI connects to an OpenAI-compatible interface.
    # We pass the ModelMesh client so that all calls are routed through
    # ModelMesh's capability pools.

    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser

    # The "model" parameter is a virtual model name that maps to a
    # ModelMesh capability pool.  LangChain does not need to know the
    # actual provider or model -- ModelMesh resolves it.
    llm = ChatOpenAI(
        model="text-generation",       # virtual model name -> ModelMesh pool
        temperature=0.7,
        max_tokens=256,
        client=modelmesh_client,       # use the ModelMesh client
    )

    # -----------------------------------------------------------------------
    # 3. Build a simple LangChain chain
    # -----------------------------------------------------------------------
    print("--- Example 1: Simple chain ---\n")

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert in {domain}. Give concise, clear explanations."),
        ("human", "{question}"),
    ])

    chain = prompt | llm | StrOutputParser()

    # Invoke the chain.  Under the hood, LangChain calls
    # client.chat.completions.create() which ModelMesh intercepts,
    # routes to the cheapest active model, and handles failover.
    result = await chain.ainvoke({
        "domain": "distributed systems",
        "question": "What is the difference between consistency and availability in the CAP theorem?",
    })

    print(f"Question: What is the difference between consistency and availability?")
    print(f"Answer  : {result[:200]}...")
    print()

    # -----------------------------------------------------------------------
    # 4. Run multiple chain invocations to demonstrate routing
    # -----------------------------------------------------------------------
    print("--- Example 2: Multiple invocations (observe routing) ---\n")

    questions = [
        {"domain": "databases", "question": "What is a B-tree?"},
        {"domain": "networking", "question": "What is DNS?"},
        {"domain": "security", "question": "What is TLS?"},
    ]

    for i, q in enumerate(questions, start=1):
        result = await chain.ainvoke(q)
        print(f"  Q{i}: {q['question']}")
        print(f"  A{i}: {result[:100]}...")
        print()

    print("Check the console output above for routing decisions.  Each call")
    print("went through ModelMesh's cost-first strategy, which selected the")
    print("cheapest active model.  If one provider had failed, ModelMesh")
    print("would have retried on another provider transparently.\n")

    # -----------------------------------------------------------------------
    # 5. Streaming with LangChain
    # -----------------------------------------------------------------------
    print("--- Example 3: Streaming with LangChain ---\n")

    print("Q: Explain what a load balancer does.\n")
    print("A: ", end="")

    async for token in chain.astream({
        "domain": "infrastructure",
        "question": "Explain what a load balancer does.",
    }):
        print(token, end="", flush=True)

    print("\n")

    # -----------------------------------------------------------------------
    # 6. Show that ModelMesh tracked everything
    # -----------------------------------------------------------------------
    print("--- ModelMesh status ---\n")
    pool_status = mesh.pool_status()
    print(f"  Pool 'text-generation': {pool_status.get('text-generation', {})}")
    print()
    print("  Active providers:")
    for pid in mesh.active_providers():
        print(f"    - {pid}")

    mesh.shutdown()
    print("\nModelMesh shut down.")


if __name__ == "__main__":
    asyncio.run(main())
