# /my_copilotkit_remote_endpoint/checkpointer.py

import json
from typing import Any, Optional


class InMemoryCheckpointer:
    """
    A simple in-memory checkpointer for CopilotKit.
    Suitable for testing purposes.
    """

    def __init__(self):
        self.storage = {}

    def set_state(self, key: str, state: Any) -> None:
        """
        Persist the state in memory.
        """
        self.storage[key] = json.dumps(state)

    def get_state(self, key: str) -> Optional[Any]:
        """
        Retrieve the state from memory.
        """
        state = self.storage.get(key)
        if state:
            return json.loads(state)
        return None

    def delete_state(self, key: str) -> None:
        """
        Delete the state from memory.
        """
        if key in self.storage:
            del self.storage[key]
