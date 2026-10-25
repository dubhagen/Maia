"""ASR and TTS through the same LiteLLM endpoint as chat."""

import datetime
import random

from bridge.reply import Reply, ReplyType
from common.log import logger
from common.media_download import MAX_FILE_BYTES, MediaTooLargeError, save_response
from common.tmp_dir import TmpDir
from config import conf
from models.litellm.endpoint import LiteLLMConfigError, litellm_api_base, litellm_api_key
from models.litellm.http_client import OpenAIHTTPClient, OpenAIHTTPError
from voice.voice import Voice

import requests


class LiteLLMVoice(Voice):
    def _client(self):
        return OpenAIHTTPClient(
            api_key=litellm_api_key(),
            api_base=litellm_api_base(),
            proxy=conf().get("proxy") or None,
            timeout=60,
        )

    def voiceToText(self, voice_file):
        model = (conf().get("asr_model") or "").strip()
        if not model:
            return Reply(ReplyType.ERROR, "asr_model is not set")
        try:
            data = self._client().audio_transcriptions(
                file_path=voice_file,
                model=model,
                api_key=litellm_api_key(),
                api_base=litellm_api_base(),
            )
        except (LiteLLMConfigError, OpenAIHTTPError, OSError) as exc:
            logger.error("[LiteLLM] voiceToText failed: %s", exc)
            return Reply(ReplyType.ERROR, "voice transcription failed")
        text = data.get("text") if isinstance(data, dict) else None
        if not isinstance(text, str):
            return Reply(ReplyType.ERROR, "voice transcription failed")
        return Reply(ReplyType.TEXT, text)

    def textToVoice(self, text):
        model = (conf().get("tts_model") or "").strip()
        if not model:
            return Reply(ReplyType.ERROR, "tts_model is not set")
        voice = (conf().get("tts_voice") or "alloy").strip() or "alloy"
        try:
            client = self._client()
            base = litellm_api_base()
            url = f"{base}/audio/speech"
            headers = {
                "Authorization": "Bearer " + litellm_api_key(),
                "Content-Type": "application/json",
            }
            if not litellm_api_key():
                headers.pop("Authorization")
            response = requests.post(
                url,
                headers=headers,
                json={"model": model, "input": text, "voice": voice},
                timeout=60,
                stream=True,
                proxies=client.proxies,
            )
        except (LiteLLMConfigError, requests.RequestException) as exc:
            logger.error("[LiteLLM] textToVoice failed: %s", exc)
            return Reply(ReplyType.ERROR, "speech synthesis failed")
        if response.status_code >= 400:
            logger.error("[LiteLLM] textToVoice HTTP %s", response.status_code)
            response.close()
            return Reply(ReplyType.ERROR, "speech synthesis failed")
        file_name = (
            TmpDir().path()
            + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            + str(random.randint(0, 1000))
            + ".mp3"
        )
        try:
            save_response(response, file_name, MAX_FILE_BYTES)
        except MediaTooLargeError:
            return Reply(ReplyType.ERROR, "speech synthesis failed")
        return Reply(ReplyType.VOICE, file_name)
