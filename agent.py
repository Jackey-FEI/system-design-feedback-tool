# agent.py
from rag_engine import get_snippets
from memory import ConversationMemory
from textwrap import indent

PROMPT_HEADER = """You are a senior system-design interviewer.
When you answer:
• Be concise yet thorough.
• Start with a one-line summary.
• Then list strengths, weaknesses, and concrete suggestions.

Context snippets (from our internal knowledge base):
--------------------
{context}
--------------------"""

PROMPT_FORMAT = """
Conversation so far:
{history}

▶︎ Candidate (latest message):
{candidate}

▶︎ Now respond as the interviewer:
"""

class DesignAgent:
    def __init__(self, mem: ConversationMemory):
        self.mem = mem

    def build_prompt(self, user_id: str, user_msg: str) -> str:
        # 1. RAG
        context = get_snippets(user_msg,2)
        # 2. Conversation history
        hist_blocks = []
        for m in self.mem.history(user_id):
            tag = "Candidate" if m["role"] == "user" else "Interviewer"
            hist_blocks.append(f"{tag}: {m['text']}")
        history_text = indent("\n".join(hist_blocks), "  ")
        # 3. Assemble
        return PROMPT_HEADER.format(context=context) + PROMPT_FORMAT.format(
            history=history_text, candidate=user_msg
        )
