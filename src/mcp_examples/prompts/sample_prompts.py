"""Example prompts registered on the FastMCP server."""

from fastmcp import FastMCP
from fastmcp.prompts import Message


def register(mcp: FastMCP) -> None:
    """Register sample prompts that demonstrate prompt generation in FastMCP."""

    @mcp.prompt
    def ask_about_topic(topic: str) -> str:
        """Create a user-facing request for an explanation of a given topic."""
        return f"Can you please explain the concept of '{topic}'?"

    @mcp.prompt
    def generate_code_request(language: str, task_description: str) -> list[Message]:
        """Generate a simple multi-message prompt for code-generation tasks."""
        return [
            Message(
                f"Write a {language} function that performs the following task: {task_description}"
            ),
            Message("I'll help you write that function.", role="assistant"),
        ]
