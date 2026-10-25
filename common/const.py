# Provider type strings. Chat always uses LiteLLM. These names stay so
# bundled plugins can still recognize a stored bot type.
LITELLM = "litellm"
OPEN_AI = "openAI"
OPENAI = "openai"
CHATGPT = "chatGPT"  # legacy alias for OPENAI
BAIDU = "baidu"
QIANFAN = "qianfan"
XUNFEI = "xunfei"
CHATGPTONAZURE = "chatGPTOnAzure"
CLAUDEAPI= "claudeAPI"
QWEN = "qwen"
QWEN_DASHSCOPE = "dashscope"
GEMINI = "gemini"
ZHIPU_AI = "zhipu"
MOONSHOT = "moonshot"
MiniMax = "minimax"
DEEPSEEK = "deepseek"
MIMO = "mimo"
CUSTOM = "custom"
MODELSCOPE = "modelscope"

# Model ids are pass-through strings on the LiteLLM endpoint. The old vendor
# catalogs are gone. These two remain because godcmd still falls back to them
# when a shorthand or an empty model is used.
GPT35 = "gpt-3.5-turbo"
GPT4_TURBO_PREVIEW = "gpt-4-turbo-preview"
