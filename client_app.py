import asyncio
import streamlit as st
from mcp_agent.app import MCPApp
from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM
from agent_state import get_agent_state
import uuid
from typing import Dict, List

class SystemDesignInterviewer:
    def __init__(self):
        self.app = MCPApp(name="system_design_interviewer")
        self.state = None
        self.agent = None
        self.llm   = None
        self.current_phase = 0
        self.system_design_topic = ""
        self.user_id = str(uuid.uuid4())
        
        # Interview phases in order
        self.phases = [
            {
                "name": "Requirements",
                "prompt": "requirements-evaluation",
                "instruction": "Let's start with requirements gathering. Please describe the functional and non-functional requirements for your system."
            },
            {
                "name": "Core Entities", 
                "prompt": "core-entities-evaluation",
                "instruction": "Now let's discuss the core entities and data models. What are the main data objects in your system?"
            },
            {
                "name": "API Design",
                "prompt": "api-design-evaluation", 
                "instruction": "Let's design the APIs. What endpoints will your system expose?"
            },
            {
                "name": "Architecture",
                "prompt": "architecture-evaluation",
                "instruction": "Now let's discuss the high-level architecture. How will you structure your system components?"
            },
            {
                "name": "Deep Dive",
                "prompt": "deep-dive-evaluation",
                "instruction": "Let's dive deeper into technical details. How will you handle scalability, performance, and reliability?"
            },
            {
                "name": "Final Evaluation",
                "prompt": "final-evaluation",
                "instruction": "Let's wrap up with a final evaluation of your overall design."
            }
        ]
    
    async def initialize_agent(self):
        """Initialize the MCP agent and connect to your server"""
         # Only run once per session

        await self.app.initialize()          # starts connection mgr, logger, etc.

        self.state = await get_agent_state(
            key="agent_state",               # stable cache key
            agent_class=Agent,
            llm_class=OpenAIAugmentedLLM,
            name="system_design_interviewer",
            instruction="""You are conducting a system-design interview.
            Follow the structured phases and provide constructive feedback.""",
            server_names=["system-design"],
        )

        self.agent = self.state.agent
        self.llm   = self.state.llm
        
        # Debug usage
        # st.write(self.state)

        if not self.agent or not self.llm:
            raise RuntimeError("Failed to initialize agent or LLM")
        
        return True
    
    async def get_phase_context(self, system_design: str) -> str:
        """Get RAG context and phase-specific prompt"""
        current_phase_info = self.phases[self.current_phase]
        # phase_name = current_phase_info["name"]
        phase_prompt_name = current_phase_info["prompt"]
        
        # Get RAG context using MCP tool
        rag_context = await self.agent.call_tool(
            "get_rag_context", 
            {"system_design": system_design}
        )
        
        # Get the phase-specific prompt using MCP prompt
        phase_prompt = await self.agent.get_prompt(
            f"{phase_prompt_name}",
            {"system_design": system_design}
        )
        
        return f"{rag_context}\n\n{phase_prompt}"
    
    async def evaluate_response(self, user_response: str) -> str:
        """Evaluate user's response for current phase"""
        current_phase_info = self.phases[self.current_phase]
        
        # Get RAG context for the user's response

        context = await self.get_phase_context(user_response)

        # Construct the evaluation prompt

        evaluation_prompt = f"""
        Based on the {current_phase_info['name']} phase evaluation criteria,
        please evaluate this response: {user_response}

        You may refer to similar system's respond answers to provide insights.
        Similary system's respond answers:
        {context}
        
        System design topic: {self.system_design_topic}
        
        Provide constructive feedback and determine if we should:
        1. Move to next phase
        2. Ask for improvements
        3. Provide hints
        
        IMPORTANT: Provide your evaluation directly as text. Do not use any tools or request human input.
        """
        
        # Use generate_str with explicit instruction to avoid tool calls
        feedback = await self.llm.generate_str(
            message=evaluation_prompt
        )
        return feedback
        

# Streamlit UI
def main():
    st.title("🎯 System Design Interview Assistant")
    st.markdown("*Automated mock interviews powered by MCP and RAG*")
    
    # Initialize session state
    if 'interviewer' not in st.session_state:
        st.session_state.interviewer = SystemDesignInterviewer()
        st.session_state.initialized = False
        st.session_state.interview_started = False
        st.session_state.conversation_history = []
    
    interviewer = st.session_state.interviewer
    
    # Sidebar for interview control
    with st.sidebar:
        st.header("Interview Control")
        
        if not st.session_state.initialized:
            if st.button("🚀 Initialize Agent"):
                with st.spinner("Connecting to MCP server..."):
                    try:
                        # Note: In real implementation, you'd need to handle async properly
                        asyncio.run(interviewer.initialize_agent())
                        st.session_state.initialized = True
                        st.success("Agent initialized successfully!")
                    except Exception as e:
                        st.error(f"Failed to initialize: {e}")
        
        if st.session_state.initialized and not st.session_state.interview_started:
            st.subheader("Start Interview")
            system_topic = st.text_input(
                "System Design Topic", 
                placeholder="e.g., Design a chat application"
            )
            
            if st.button("📋 Start Interview") and system_topic:
                interviewer.system_design_topic = system_topic
                st.session_state.interview_started = True
                st.session_state.conversation_history.append({
                    "role": "interviewer",
                    "content": f"Welcome! Today we'll design: {system_topic}. {interviewer.phases[0]['instruction']}"
                })
                st.rerun()
        
        if st.session_state.interview_started:
            st.subheader("Interview Progress")
            current_phase = interviewer.phases[interviewer.current_phase]
            st.write(f"**Current Phase:** {current_phase['name']}")
            
            # Progress bar
            progress = (interviewer.current_phase + 1) / len(interviewer.phases)
            st.progress(progress)
            
            # Phase navigation
            col1, col2 = st.columns(2)
            with col1:
                if st.button("⬅️ Previous") and interviewer.current_phase > 0:
                    interviewer.current_phase -= 1
                    st.rerun()
            
            with col2:
                if st.button("➡️ Next") and interviewer.current_phase < len(interviewer.phases) - 1:
                    interviewer.current_phase += 1
                    current_phase = interviewer.phases[interviewer.current_phase]
                    st.session_state.conversation_history.append({
                        "role": "interviewer", 
                        "content": current_phase['instruction']
                    })
                    st.rerun()
    
    # Main chat interface
    if st.session_state.interview_started:
        st.header(f"💬 Interview: {interviewer.system_design_topic}")
        
        # Display conversation history
        for msg in st.session_state.conversation_history:
            if msg["role"] == "interviewer":
                with st.chat_message("assistant", avatar="🤖"):
                    st.write(msg["content"])
            else:
                with st.chat_message("user", avatar="👤"):
                    st.write(msg["content"])
        
        # User input
        user_input = st.chat_input("Your response...")
        
        if user_input:
            # Add user message to history
            st.session_state.conversation_history.append({
                "role": "user",
                "content": user_input
            })
            
            # Process the response with proper error handling
            try:
                with st.spinner("Generating feedback..."):
                    feedback = asyncio.run(interviewer.evaluate_response(user_input))
                
                # Add interviewer response to history
                st.session_state.conversation_history.append({
                    "role": "interviewer",
                    "content": feedback
                })
                
            except Exception as e:
                st.error(f"Error generating feedback: {e}")
                # Add error message to conversation
                st.session_state.conversation_history.append({
                    "role": "interviewer",
                    "content": "I apologize, but I encountered an error processing your response. Please try again."
                })
            
            # Rerun ONLY after everything is processed and stored in session_state
            st.rerun()

    else:
        # Welcome screen
        st.markdown("""
        ## Welcome to the System Design Interview Assistant! 🚀
        
        This tool provides automated mock system design interviews using:
        - **MCP (Model Context Protocol)** for structured prompts
        - **RAG (Retrieval Augmented Generation)** for contextual feedback
        - **Automated phase progression** through interview stages
        
        ### How it works:
        1. **Initialize** the agent connection
        2. **Choose** your system design topic
        3. **Progress** through structured interview phases
        4. **Receive** real-time feedback and guidance
        
        Get started by initializing the agent in the sidebar! 👈
        """)

if __name__ == "__main__":
    main()