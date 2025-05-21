# server.py
import uuid
from fastmcp import FastMCP, Context
from memory import ConversationMemory
from agent import DesignAgent

memory = ConversationMemory(max_turns=10)
agent = DesignAgent(memory)
CLAUDE_COMMAND = "claude.respond"   # Claude client must listen for this

mcp = FastMCP("system-design")

@mcp.tool()
async def get_rag_context(user_id: str, system_design: str, ctx: Context) -> str:
    """
    Get a response from the RAG engine.
    This tool is used to get the response from the RAG engine.
    """
    if not system_design:
        return {"error": "Missing system_design"}

    user_id = user_id or str(uuid.uuid4())
    
    # Build prompt with memory + RAG
    prompt = agent.build_prompt(user_id, system_design)
    
    return prompt

@mcp.tool()
async def get_sampling_response(user_id: str, system_design: str, ctx: Context) -> str:
    """
    Check if the system design is valid.
    This tool is used to improve the prompt by sampling.

    This method is limited supported by MCP clients. Disable this tool on Claude Desktop App.
    """
    if not system_design:
        return {"error": "Missing system_design"}
    
    response = await ctx.sample(
        messages = "This is a system design for a chatbot. Please provide feedback in less than 40 words on the design.",
        system_prompt ="You are a helpful assistant that provides concise feedback on system designs based on the user's input.",
        temperature=0.7,
        max_tokens=150
    )

    return response.text.strip().lower()

@mcp.tool()
async def design_feedback(user_id: str, system_design: str, ctx: Context) -> dict:
    """
    Get feedback on a system design from Claude.
    
    Args:
        user_id: Optional user ID. If not provided, a new UUID will be generated.
        system_design: User's system design which is user's input.
        
    Returns:
        dict: Contains either feedback or error message.
    """
    if not system_design:
        return {"error": "Missing system_design"}

    user_id = user_id or str(uuid.uuid4())
    
    # Build prompt with memory + RAG
    prompt = agent.build_prompt(user_id, system_design)

    # Ask Claude client
    response = await ctx.sample(
        messages = prompt,
        system_prompt ="You are a helpful assistant that provides concise feedback on system designs based on the user's input.",
        temperature=0.7,
        max_tokens=300
    )
    
    # Process the LLM's response
    feedback = response.text.strip().lower()

    # Store into memory
    memory.add(user_id, "user", system_design)
    memory.add(user_id, "assistant", feedback)
    return {"feedback": feedback}

if __name__ == "__main__":
    mcp.run()
