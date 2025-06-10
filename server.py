# server.py
import uuid
from fastmcp import FastMCP, Context
from memory import ConversationMemory
from agent import DesignAgent
from rag_engine import get_snippets
memory = ConversationMemory(max_turns=10)
agent = DesignAgent(memory)
CLAUDE_COMMAND = "claude.respond"   # Claude client must listen for this

mcp = FastMCP("system-design")

@mcp.prompt(
    name="role-definition",
    description="role-definition of the MCP server, only used at the beginning of the conversation",
    tags={"background"}
)
async def role_definition(ctx: Context) -> str:
    """
    Get the role definition of the MCP server.
    """
    return """
    You are a senior software engineer specializing in system design with extensive experience in:
    - Designing scalable distributed systems
    - Evaluating architectural decisions
    - Providing actionable feedback on system designs
    
    Your responsibilities:
    1. Evaluate system designs objectively using industry best practices
    2. Leverage RAG engine context to provide relevant examples and patterns
    3. Offer constructive feedback based on established criteria
    4. Guide users through iterative design improvements
    5. Maintain professionalism and avoid disclosing internal evaluation metrics

    You should never disclose your answers, except user explicitly ask you to show your answer.
    """

@mcp.prompt(
    name="requirements-evaluation",
    description="Evaluate functional and non-functional requirements",
    tags={"evaluation"}
)
async def evaluate_requirements(ctx: Context, system_design: str) -> str:
    return """
    Evaluate {{system-design}} requirements:

    Functional Requirements ("Users should be able to..."):
    - Core features and user interactions
    - Business operations
    - Data operations

    Non-Functional Requirements ("System should be/have..."):
    - Performance metrics (e.g., "respond within X ms")
    - Scalability targets (e.g., "handle X users")
    - Reliability goals 

    Evaluate:
    - Completeness and clarity
    - Technical feasibility
    - Requirement conflicts
    - Trade-offs

   You should never disclose your answers, except that user explicitly ask you to show your answer.
    You may ask user to improve their answer if it is far away from your expected answer.
    """

@mcp.prompt(
    name="core-entities-evaluation",
    description="Evaluate system core entities and data models",
    tags={"evaluation"}
)
async def evaluate_core_entities(ctx: Context, system_design: str) -> str:
    return """
    Review the core entities for {{system-design}} considering entity completeness
    Core entities are the fundamental components of the system's data model.
    They can also be thought of as the major tables in the database.
    
    Evaluate:
    - Entity completeness and reasonability.

    You should never disclose your answers, except that user explicitly ask you to show your answer.
    You may ask user to improve their answer if it is far away from your expected answer.
    """

@mcp.prompt(
    name="api-design-evaluation",
    description="Evaluate API design and interfaces",
    tags={"evaluation"}
)
async def evaluate_api_design(ctx: Context, system_design: str) -> str:
    return """
    Analyze the API design for {{system-design}} focusing on:
    1. RESTful principles adherence
    2. Interface consistency
    3. Error handling
    
    Review:
    - Endpoint design and naming
    - Request/response formats
    - Authentication/authorization
    - Rate limiting and quotas

    You should never disclose your answers, except that user explicitly ask you to show your answer.
    You may ask user to improve their answer if it is far away from your expected answer.
    """

@mcp.prompt(
    name="architecture-evaluation",
    description="Evaluate high-level architecture",
    tags={"evaluation"}
)
async def evaluate_architecture(ctx: Context, system_design: str) -> str:
    return """
    Assess the high-level architecture for {{system-design}} considering:
    1. Component separation and responsibilities
    2. Scalability patterns
    3. Reliability mechanisms
    The primary goal of this part is to design an architecture 
    that satisfies the API designed and, thus, the requirements user identified. 
    If applicable, user may present their drawing of the architecture.
    
    Evaluate:
    - Service functionalities based on requirements
    - Infrastructure choices
    - System constraints
    """

@mcp.prompt(
    name="deep-dive-evaluation",
    description="Evaluate detailed technical decisions",
    tags={"evaluation"}
)
async def evaluate_deep_dive(ctx: Context, system_design: str) -> str:
    return """
    Deep dive analysis for {{system-design}} focusing on:
    1. Non-functional requirements implementation
       - Scalability solutions (e.g., horizontal scaling, sharding)
       - Performance optimizations (e.g., caching strategies)
       - Reliability measures

    2. Edge cases and bottlenecks
       - System limitations
       - Potential failure points
       - Load handling strategies

    3. Technical improvements
       - Data access patterns
       - System optimizations
       - Infrastructure decisions

    This part is quite hard for entry and mid level software engineers.
    If user are a mid-level or below engineer (if not specified), they are not required to be perfect or answer all the considerations.

    You should never disclose your answers, except that user explicitly ask you to show your answer.
    You may ask user to improve their answer if it is far away from your expected answer.
    """

@mcp.prompt(
    name="final-evaluation",
    description="Provide overall evaluation and grading",
    tags={"evaluation"}
)
async def final_evaluation(ctx: Context, system_design: str) -> str:
    return """
    Provide comprehensive evaluation for {{system-design}} covering:
    1. Overall design quality
    2. Technical depth
    3. Problem-solving approach
    4. Communication clarity
    
    Highlight:
    - Strong design decisions
    - Areas for improvement
    - Technical trade-offs
    - Future considerations
    """

@mcp.prompt(
    name="system-design-feedback-procedure",
    description="procedure of the system design feedback",
    tags={"procedure"}
)
async def system_design_feedback_procedure(ctx: Context, system_design: str) -> str:
    """
    Get the procedure of an system design interview.
    Use this prompt after the role definition.
    """
    return """
    For {{system-design}}, follow this iterative feedback process:

    1. Requirements Phase
       - Collect functional and non-functional requirements
       - Evaluate using requirements-evaluation criteria
       - Provide feedback and recommendations
       - Allow revision or proceed to next phase

    2. Core Entities Phase
       - Review proposed data models and entities
       - Evaluate using core-entities-evaluation criteria
       - Provide feedback on relationships and schema
       - Allow revision or proceed to next phase

    3. API Design Phase
       - Examine API specifications
       - Evaluate using api-design-evaluation criteria
       - Provide feedback on endpoints and interfaces
       - Allow revision or proceed to next phase

    4. Architecture Phase
       - Review high-level system architecture
       - Evaluate using architecture-evaluation criteria
       - Provide feedback on components and patterns
       - Allow revision or proceed to next phase

    5. Deep Dive Phase
       - Analyze technical implementation details
       - Focus on non-functional requirements
       - Evaluate using deep-dive-evaluation criteria
       - Allow revision or proceed to final phase

    6. Final Evaluation
       - Provide comprehensive assessment
       - Highlight strengths and areas for improvement
       - Give overall grading based on all phases
       - Summarize key learning points

    Note: At each phase:
    - Use RAG context for relevant examples
    - Provide specific, actionable feedback
    - Allow iterative improvements
    - Maintain professional evaluation standards
    """
    
@mcp.tool()
async def get_rag_context(user_id: str, system_design: str, ctx: Context) -> str:
    """
    Get a response from the RAG engine.
    This tool is used to get the response from the RAG engine.
    By using the context from the RAG engine, you should evaluate the system design and provide feedback.
    You are not allowed to disclose your expected output.
    """
    try:
        if not system_design:
            return {"error": "Missing system_design"}

        user_id = user_id or str(uuid.uuid4())
        
        # Build prompt with memory + RAG
        prompt = get_snippets(system_design, 2)
        
        return prompt
    except Exception as e:
        return f"Error in get_rag_context: {str(e)}"

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
