import os
from langchain_openai import ChatOpenAI


def get_llm() -> ChatOpenAI:
    kwargs = {
        "api_key": os.environ["LLM_API_KEY"],
        "model": os.environ.get("LLM_MODEL", "gpt-4o"),
        "streaming": True,
    }
    base_url = os.environ.get("LLM_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)
