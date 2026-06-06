from __future__ import annotations


def build_cascade():
    """Shared cascade builder — Anthropic → Gemini → DeepSeek → Qwen → Ollama-only.

    Single source of truth used by both web.py and main.py.
    """
    from drive_organizer.ai.cascade import AICascade
    from drive_organizer.ai.ollama_provider import OllamaProvider
    from drive_organizer.config import settings

    if settings.anthropic_api_key:
        from drive_organizer.ai.haiku_provider import HaikuProvider
        from drive_organizer.ai.opus_provider import OpusProvider
        haiku, opus = HaikuProvider(), OpusProvider()
    elif settings.gemini_api_key:
        from drive_organizer.ai.gemini_provider import GeminiFlashProvider, GeminiProProvider
        haiku, opus = GeminiFlashProvider(), GeminiProProvider()
    elif settings.deepseek_api_key:
        from drive_organizer.ai.deepseek_provider import DeepSeekFlashProvider, DeepSeekProProvider
        haiku, opus = DeepSeekFlashProvider(), DeepSeekProProvider()
    elif settings.dashscope_api_key:
        from drive_organizer.ai.qwen_provider import QwenFlashProvider, QwenProProvider
        haiku, opus = QwenFlashProvider(), QwenProProvider()
    else:
        from drive_organizer.ai.haiku_provider import HaikuProvider
        from drive_organizer.ai.opus_provider import OpusProvider
        haiku, opus = HaikuProvider(), OpusProvider()

    return AICascade(ollama=OllamaProvider(), haiku=haiku, opus=opus)
