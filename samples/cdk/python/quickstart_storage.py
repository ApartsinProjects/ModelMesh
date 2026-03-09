"""Quickstart: Create a KeyValueStorage and perform save/load/list/delete.

Demonstrates the full CRUD cycle using the in-memory backend of the
KeyValueStorage specialized class.
"""

import asyncio

from modelmesh.cdk import KeyValueStorage, KeyValueStorageConfig
from modelmesh.interfaces.storage import StorageEntry


async def main() -> None:
    storage = KeyValueStorage(KeyValueStorageConfig(
        backend="memory",
        format="json",
    ))

    # Save
    entry = StorageEntry(
        key="config/app-settings",
        data=b'{"theme": "dark", "lang": "en"}',
        metadata={"source": "quickstart"},
    )
    await storage.save("config/app-settings", entry)
    print("Saved entry.")

    # Load
    loaded = await storage.load("config/app-settings")
    print(f"Loaded: {loaded.data.decode('utf-8')}")

    # List
    keys = await storage.list("config/")
    print(f"Keys: {keys}")

    # Delete
    deleted = await storage.delete("config/app-settings")
    print(f"Deleted: {deleted}")


if __name__ == "__main__":
    asyncio.run(main())
