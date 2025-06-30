import asyncio
import gradio as gr
from mcp_agent.app import MCPApp
from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM
from agent_state import get_agent_state
import uuid
from typing import Dict, List, Tuple
from inspect import iscoroutine
import threading

def write_to_file(content, filename='output.txt'):
    with open(filename, 'a') as f:
        f.write(content + '\n')

def _dump(label: str, agent):
    try:
        loop_now = asyncio.get_running_loop()
    except RuntimeError:
        loop_now = "no loop"
    
    try:
        # aiohttp.ClientSession still carries its loop reference
        agent_loop = agent._client_session._loop
        closed = agent._client_session.closed
    except AttributeError:
        agent_loop = "n/a"
        closed = "n/a"

    write_to_file(f"{label:<12} loop_now={id(loop_now)} "
          f"agent_loop={id(agent_loop) if agent_loop!='n/a' else agent_loop} "
          f"closed={closed}")

class SystemDesignInterviewer:
    def __init__(self):
        self.state = None
        self.agent = None
        self.llm   = None
        self.current_phase = 0
        self.system_design_topic = ""
        self.user_id = str(uuid.uuid4())
        self.conversation_history = []
        self.interview_started = False
        self.initialized = False
        
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
        _dump("init_agent", self.agent)
        """Initialize the MCP agent and connect to your server"""
         # Only run once per session

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
        
        if not self.agent or not self.llm:
            raise RuntimeError("Failed to initialize agent or LLM")
        
        self.initialized = True
        return True
    
    async def get_phase_context(self, system_design: str) -> str:
        """Get RAG context and phase-specific prompt"""
        current_phase_info = self.phases[self.current_phase]
        phase_prompt_name = current_phase_info["prompt"]
        
        # Get RAG context using MCP tool
        rag_context = await self.agent.call_tool(
            "get_rag_context", 
            {
                "user_id": self.user_id,
                "system_design": system_design
            }
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
        # context = await self.get_phase_context(user_response)

        # Construct the evaluation prompt
        # evaluation_prompt = f"""
        # Based on the {current_phase_info['name']} phase evaluation criteria,
        # please evaluate this response: {user_response}

        # You may refer to similar system's respond answers to provide insights.
        # Similary system's respond answers:
        # {context}
        
        # System design topic: {self.system_design_topic}
        
        # Provide constructive feedback and determine if we should:
        # 1. Move to next phase
        # 2. Ask for improvements
        # 3. Provide hints
        
        # IMPORTANT: Provide your evaluation directly as text. Do not use any tools or request human input.
        # """

        phase_prompt = await self.agent.get_prompt(
            f"{current_phase_info['name']}",
            {"system_design": self.system_design_topic}
        )

        evaluation_prompt = f"""
        Based on the {current_phase_info['name']} phase evaluation criteria,
        please evaluate this response: {user_response} based on requirement of criteria:
        {phase_prompt}.

        You should refer to similar system's respond answers to review user's answer and provide insights.
        Use get_rag_context tool to get similar system's respond answers.
        
        System design topic: {self.system_design_topic}

        Then, determine if we should:
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
    
    # For debug purpose
    async def ensure_connection(self, testId: str):
        """Ensure MCP connection is still active"""
        _dump("ensure_conn", self.agent)
        try:
            # Test connection with a simple call
            await self.agent.call_tool("get_rag_context", {"user_id": testId, "system_design": "test"})
            return True
        except Exception as e:
            print(f"Connection lost, reinitializing: {e}")
            return True

# Global interviewer instance
interviewer = SystemDesignInterviewer()

def run_async(coro):
    """Helper function to run async functions in Gradio"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're in an async context, create a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)

async def initialize_system():
    """Initialize the MCP system"""
    global interviewer
    try:
        # Initialize the app and interviewer
        app = MCPApp(name="system_design_interviewer")
        
        async def init_async():
            await app.initialize()
            await interviewer.initialize_agent()
            return "✅ System initialized successfully!"
        
        result = await init_async()
        return result
    except Exception as e:
        return f"❌ Initialization failed: {str(e)}"

def start_interview(topic: str):
    """Start a new interview with the given topic"""
    global interviewer
    if not interviewer.initialized:
        return "❌ Please initialize the system first!", "", 0, "Not Started"
    
    if not topic.strip():
        return "❌ Please enter a system design topic!", "", 0, "Not Started"
    
    interviewer.system_design_topic = topic
    interviewer.interview_started = True
    interviewer.current_phase = 0
    interviewer.conversation_history = []
    
    # Add initial message
    initial_message = f"Welcome! Today we'll design: {topic}. {interviewer.phases[0]['instruction']}"
    interviewer.conversation_history.append({
        "role": "interviewer",
        "content": initial_message
    })
    
    # Format conversation for display
    conversation = format_conversation(interviewer.conversation_history)
    current_phase = interviewer.phases[interviewer.current_phase]
    progress = (interviewer.current_phase + 1) / len(interviewer.phases)
    
    return "✅ Interview started!", conversation, progress, current_phase['name']

def format_conversation(history):
    """Format conversation history for display"""
    formatted = ""
    for msg in history:
        if msg["role"] == "interviewer":
            formatted += f"🤖 **Interviewer:** {msg['content']}\n\n"
        else:
            formatted += f"👤 **You:** {msg['content']}\n\n"
    return formatted

async def submit_response(user_input: str, conversation_history: str):
    """Submit user response and get feedback"""
    global interviewer
    
    if not interviewer.interview_started:
        return "❌ Please start an interview first!", conversation_history, 0, "Not Started"
    
    if not user_input.strip():
        return "❌ Please enter a response!", conversation_history, 0, interviewer.phases[interviewer.current_phase]['name']
    
    try:
        # Add user message to history
        interviewer.conversation_history.append({
            "role": "user",
            "content": user_input
        })
        
        # Get feedback asynchronously
        async def get_feedback():
            return await interviewer.evaluate_response(user_input)
        
        feedback = await get_feedback()
        
        # Add interviewer response to history
        interviewer.conversation_history.append({
            "role": "interviewer",
            "content": feedback
        })
        
        # Format conversation for display
        conversation = format_conversation(interviewer.conversation_history)
        current_phase = interviewer.phases[interviewer.current_phase]
        progress = (interviewer.current_phase + 1) / len(interviewer.phases)
        
        return "✅ Response processed!", conversation, progress, current_phase['name']
        
    except Exception as e:
        error_msg = f"❌ Error processing response: {str(e)}"
        interviewer.conversation_history.append({
            "role": "interviewer",
            "content": "I apologize, but I encountered an error processing your response. Please try again."
        })
        conversation = format_conversation(interviewer.conversation_history)
        current_phase = interviewer.phases[interviewer.current_phase]
        progress = (interviewer.current_phase + 1) / len(interviewer.phases)
        return error_msg, conversation, progress, current_phase['name']

def navigate_phase(direction: str):
    """Navigate to previous or next phase"""
    global interviewer
    
    if not interviewer.interview_started:
        return "❌ Please start an interview first!", "", 0, "Not Started"
    
    if direction == "previous" and interviewer.current_phase > 0:
        interviewer.current_phase -= 1
    elif direction == "next" and interviewer.current_phase < len(interviewer.phases) - 1:
        interviewer.current_phase += 1
        # Add phase instruction to conversation
        current_phase = interviewer.phases[interviewer.current_phase]
        interviewer.conversation_history.append({
            "role": "interviewer",
            "content": current_phase['instruction']
        })
    
    conversation = format_conversation(interviewer.conversation_history)
    current_phase = interviewer.phases[interviewer.current_phase]
    progress = (interviewer.current_phase + 1) / len(interviewer.phases)
    
    return f"✅ Moved to {current_phase['name']} phase", conversation, progress, current_phase['name']

def create_interface():
    """Create the Gradio interface"""
    with gr.Blocks(title="System Design Interview Assistant", theme=gr.themes.Soft()) as demo:
        gr.Markdown("""
        # 🎯 System Design Interview Assistant
        *Automated mock interviews powered by MCP and RAG*
        
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
        """)
        
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## 🔧 System Control")
                
                # System initialization
                init_btn = gr.Button("🚀 Initialize System", variant="primary")
                init_status = gr.Textbox(label="Initialization Status", interactive=False)
                
                gr.Markdown("## 📋 Interview Setup")
                
                # Interview setup
                topic_input = gr.Textbox(
                    label="System Design Topic",
                    placeholder="e.g., Design a chat application",
                    lines=2
                )
                start_btn = gr.Button("📋 Start Interview", variant="secondary")
                
                gr.Markdown("## 📊 Interview Progress")
                
                # Progress tracking
                progress_bar = gr.Slider(
                    label="Progress",
                    minimum=0,
                    maximum=1,
                    value=0,
                    interactive=False
                )
                current_phase_display = gr.Textbox(
                    label="Current Phase",
                    value="Not Started",
                    interactive=False
                )
                
                # Phase navigation
                with gr.Row():
                    prev_btn = gr.Button("⬅️ Previous")
                    next_btn = gr.Button("➡️ Next")
                
                # Status display
                status_display = gr.Textbox(label="Status", interactive=False)
            
            with gr.Column(scale=2):
                gr.Markdown("## 💬 Interview Conversation")
                
                # Conversation display
                conversation_display = gr.Markdown(
                    value="*Interview conversation will appear here...*",
                    height=400
                )
                
                # User input
                user_input = gr.Textbox(
                    label="Your Response",
                    placeholder="Type your response here...",
                    lines=3
                )
                submit_btn = gr.Button("📤 Submit Response", variant="primary")
        
        # Event handlers
        init_btn.click(
            fn=initialize_system,
            outputs=[init_status]
        )
        
        start_btn.click(
            fn=start_interview,
            inputs=[topic_input],
            outputs=[status_display, conversation_display, progress_bar, current_phase_display]
        )
        
        submit_btn.click(
            fn=submit_response,
            inputs=[user_input, conversation_display],
            outputs=[status_display, conversation_display, progress_bar, current_phase_display]
        ).then(
            fn=lambda: "",  # Clear input after submission
            outputs=[user_input]
        )
        
        user_input.submit(  # Allow Enter key to submit
            fn=submit_response,
            inputs=[user_input, conversation_display],
            outputs=[status_display, conversation_display, progress_bar, current_phase_display]
        ).then(
            fn=lambda: "",
            outputs=[user_input]
        )
        
        prev_btn.click(
            fn=lambda: navigate_phase("previous"),
            outputs=[status_display, conversation_display, progress_bar, current_phase_display]
        )
        
        next_btn.click(
            fn=lambda: navigate_phase("next"),
            outputs=[status_display, conversation_display, progress_bar, current_phase_display]
        )
    
    return demo

if __name__ == "__main__":
    demo = create_interface()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        debug=True
    )