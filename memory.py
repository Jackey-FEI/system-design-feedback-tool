# memory.py
from collections import defaultdict
from typing import List, Dict

class ConversationMemory:
    """
    Keeps a list[dict] for each user:
        {"role": "user" | "assistant", "text": "..."}
    """

    def __init__(self, max_turns: int = 12):
        self._store: Dict[str, List[dict]] = defaultdict(list)
        self.max_turns = max_turns

    def add(self, user_id: str, role: str, text: str):
        convo = self._store[user_id]
        convo.append({"role": role, "text": text})
        # clip history
        if len(convo) > self.max_turns * 2:  # user+assistant = 2 msgs per turn
            self._store[user_id] = convo[-self.max_turns * 2 :]

    def history(self, user_id: str) -> List[dict]:
        return self._store[user_id]
