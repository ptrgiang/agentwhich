from .claude import ClaudeResolver
from .codex import CodexResolver
from .copilot import CopilotResolver
from .gemini import GeminiResolver

RESOLVERS = {
    'codex': CodexResolver(),
    'claude': ClaudeResolver(),
    'copilot': CopilotResolver(),
    'gemini': GeminiResolver(),
}

__all__ = ['RESOLVERS', 'ClaudeResolver', 'CodexResolver', 'CopilotResolver', 'GeminiResolver']
