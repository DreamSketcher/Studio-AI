"""Рабочие пространства (Workspace tabs)."""
from .base_workspace import BaseWorkspace
from .chat_workspace import ChatBubble, ChatWorkspace
from .image_workspace import ImageWorkspace
from .pipeline_workspace import PipelineWorkspace
from .tts_workspace import TTSWorkspace

__all__ = [
    "BaseWorkspace",
    "TTSWorkspace",
    "ChatWorkspace",
    "ImageWorkspace",
    "PipelineWorkspace",
    "ChatBubble",
]
