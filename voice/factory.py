"""Voice factory. The only engine is the LiteLLM audio API."""


def create_voice(voice_type):
    """Return the LiteLLM voice client.

    ``voice_type`` is accepted for old call sites. An empty ASR/TTS model
    makes the matching method return an error reply rather than calling out.
    """
    del voice_type
    from voice.litellm_voice import LiteLLMVoice
    return LiteLLMVoice()
