from .claude import ClaudeResolver
from .codex import CodexResolver
from .gemini import GeminiResolver

RESOLVERS = {
    'codex': CodexResolver(),
    'claude': ClaudeResolver(),
    'gemini': GeminiResolver(),
}

__all__ = ['RESOLVERS', 'ClaudeResolver', 'CodexResolver', 'GeminiResolver']
