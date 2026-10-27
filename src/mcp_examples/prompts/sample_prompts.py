
from fastmcp import FastMCP
from fastmcp.prompts import Message

def register(mcp: FastMCP) -> None:
    # Basic prompt returning a string (converted to user message automatically)
    @mcp.prompt
    def ask_about_topic(topic: str) -> str:
        """Generates a user message asking for an explanation of a topic."""
        return f"Can you please explain the concept of '{topic}'?"
    
    # Prompt returning multiple messages
    @mcp.prompt
    def generate_code_request(language: str, task_description: str) -> list[Message]:
        """Generates a conversation for code generation."""
        return [
            Message(f"Write a {language} function that performs the following task: {task_description}"),
            Message("I'll help you write that function.", role="assistant"),
        ]
