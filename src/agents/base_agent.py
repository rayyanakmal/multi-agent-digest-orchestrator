"""Base agent class for all agents in the orchestration"""

from abc import ABC, abstractmethod
from src.models.contracts import AgentMessage, RunContext


class BaseAgent(ABC):
    """Abstract base class for all agents in the daily digest system"""

    def __init__(self, name: str):
        """Initialize base agent
        
        Args:
            name: Agent identifier (e.g., 'fetcher', 'summarizer')
        """
        self.name = name
        self.retry_count = 0

    @abstractmethod
    def execute(self, context: RunContext, input_data: dict) -> AgentMessage:
        """Execute agent logic and return result message
        
        Args:
            context: Current run context
            input_data: Input data for this agent
            
        Returns:
            AgentMessage: Result message with status and payload
        """
        pass

    def create_message(self, context: RunContext, intent: str, status: str = "pending") -> AgentMessage:
        """Create a message for this agent
        
        Args:
            context: Run context
            intent: Operation intent
            status: Message status (pending, success, error)
            
        Returns:
            AgentMessage: New message
        """
        context.step_counter += 1
        return AgentMessage(
            run_id=context.run_id,
            step_id=context.step_counter,
            actor=self.name,
            intent=intent,
            payload={},
            status=status
        )
