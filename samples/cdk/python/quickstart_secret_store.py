"""Quickstart: Create a FileSecretStore and resolve a key from a .env file.

Demonstrates reading secrets from a dotenv file using the FileSecretStore
specialized class with caching enabled.
"""

from modelmesh.cdk import FileSecretStore, FileSecretStoreConfig


def main() -> None:
    store = FileSecretStore(FileSecretStoreConfig(
        file_path=".env",
        file_format="dotenv",
        cache_ttl_ms=60_000,
        fail_on_missing=True,
    ))

    try:
        api_key = store.get("OPENAI_API_KEY")
        print(f"Resolved API key: {api_key[:8]}...")
    except KeyError as exc:
        print(f"Secret not found: {exc}")


if __name__ == "__main__":
    main()
