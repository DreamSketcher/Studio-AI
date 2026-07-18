"""Рабочие пространства (Workspace tabs)."""
from .base_workspace import BaseWorkspace
from .chat_workspace import ChatBubble, ChatWorkspace
from .pipeline_workspace import PipelineWorkspace
from .tts_workspace import TTSWorkspace

__all__ = ["BaseWorkspace", "TTSWorkspace", "ChatWorkspace", "PipelineWorkspace", "ChatBubble"]
