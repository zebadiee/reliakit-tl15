import os
from enum import Enum
from reliakit.memory_db import db_session, MemorySnapshot
import json

class ModelType(Enum):
    GEMINI = "gemini"
    OLLAMA = "ollama"
    CLAUDE = "claude"

class ModelArbiter:
    """Handles model selection and fallback logic"""
    def __init__(self):
        self.preferred_model = self._get_initial_model()
        self.fallback_order = [
            ModelType.GEMINI,
            ModelType.CLAUDE, 
            ModelType.OLLAMA
        ]

    def _get_initial_model(self):
        """Determine initial model based on environment"""
        if os.getenv("GEMINI_API_KEY"):
            return ModelType.GEMINI
        return ModelType.OLLAMA

    def get_model_for_agent(self, agent_name):
        """Get appropriate model for given agent"""
        # Placeholder - could implement agent-specific model preferences
        return self.preferred_model

    def handle_fallback(self, error):
        """Handle model errors by falling back to next available model"""
        current_index = self.fallback_order.index(self.preferred_model)
        if current_index + 1 < len(self.fallback_order):
            self.preferred_model = self.fallback_order[current_index + 1]
            print(f"Falling back to {self.preferred_model.value}")
            return True
        return False

def main():
    arbiter = ModelArbiter()
    print(f"Initial model: {arbiter.preferred_model.value}")

    # Example usage
    try:
        # Simulate API call failure
        raise Exception("API Error")
    except Exception as e:
        arbiter.handle_fallback(e)
        print(f"New model: {arbiter.preferred_model.value}")

if __name__ == "__main__":
    main()