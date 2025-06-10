import asyncio
from uuid import uuid4
from mcp_agent.agents.agent import Agent

async def smoke_test():
    print("🔍 Starting MCP Server Smoke Test...")
    
    try:
        # Create and initialize agent (similar to agent_state.py)
        agent = Agent(
            connection_persistence=True,
            name="system_design_interviewer",  # This should match your server name
            server_names=["system-design"]
        )
        await agent.initialize()
        print("✅ Successfully connected to MCP server")
        
        # Test 1: Prompt rendering
        print("\n📝 Testing prompt rendering...")
        try:
            prompt_result = await agent.get_prompt(
                "requirements-evaluation", 
                {"system_design": "foo bar"}
            )
            print(f"✅ Prompt render successful: {prompt_result}")
        except Exception as e:
            print(f"❌ Prompt render failed: {e}")
        
        # Test 2: Tool call
        print("\n🔧 Testing tool call...")
        try:
            tool_result = await agent.call_tool(
                "get_rag_context", 
                {
                    "user_id": str(uuid4()), 
                    "system_design": "foo bar"
                }
            )
            print(f"✅ Tool call successful: {tool_result}")
        except Exception as e:
            print(f"❌ Tool call failed: {e}")
            
        # Clean up
        await agent.close()
        print("\n🎉 Smoke test completed!")
        
    except Exception as e:
        print(f"💥 Connection failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(smoke_test())