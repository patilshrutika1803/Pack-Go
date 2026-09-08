import os
import re
from typing import Any
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, BaseMessage
from logger.logging import get_logger

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")
logger = get_logger(__name__)

def build_structured_output(llm, schema):
    """Build structured output with the protocol supported by each provider."""
    if isinstance(llm, ChatGroq):
        return llm.with_structured_output(schema, method="json_schema")
    return llm.with_structured_output(schema)

def get_primary_llm():
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        logger.warning("GROQ_API_KEY is not set.")
    return ChatGroq(model="openai/gpt-oss-120b", api_key=groq_api_key, temperature=0.0)

def get_fallback_llm():
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        logger.warning("GOOGLE_API_KEY is not set.")
    return ChatGoogleGenerativeAI(model="gemini-3.5-flash", api_key=google_api_key, temperature=0.0)

def _sanitize_messages(args: tuple) -> tuple:
    """
    Gemini rejects requests that contain empty HumanMessages ('contents are required').
    This helper strips any HumanMessage whose content is empty/whitespace-only
    from the first positional argument if it is a list of messages.
    All other args are passed through unchanged.
    """
    if not args:
        return args
    first_arg = args[0]
    if isinstance(first_arg, list) and all(isinstance(m, BaseMessage) for m in first_arg):
        cleaned = [
            m for m in first_arg
            if not (isinstance(m, HumanMessage) and not str(m.content).strip())
        ]
        if len(cleaned) < len(first_arg):
            logger.warning(
                f"Removed {len(first_arg) - len(cleaned)} empty HumanMessage(s) "
                "before Gemini fallback invocation."
            )
        return (cleaned,) + args[1:]
    return args

def _safe_exception_message(exception: Exception) -> str:
    message = str(exception)
    for environment_name in ("GROQ_API_KEY", "GOOGLE_API_KEY"):
        secret = os.getenv(environment_name)
        if secret:
            message = message.replace(secret, "[REDACTED]")
    message = re.sub(
        r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+",
        r"\1[REDACTED]",
        message,
    )
    return re.sub(
        r"(?i)((?:api[_ -]?key|token|secret|password)\s*[:=]\s*)[\"']?[^\"'\s,}]+",
        r"\1[REDACTED]",
        message,
    )

def invoke_with_fallback(chain_builder, *args, **kwargs):
    """
    Tries to build and invoke the chain with the primary Groq LLM.
    If Groq is rate-limited or its configured model is unavailable, it builds and
    invokes the chain with Gemini instead.
    Empty HumanMessages are stripped before the Gemini call to avoid 'contents are required'.

    chain_builder is a function that takes an LLM instance and returns a runnable chain
    (e.g., lambda llm: llm.with_structured_output(Schema))
    """
    try:
        llm = get_primary_llm()
        chain = chain_builder(llm)
        return chain.invoke(*args, **kwargs)
    except Exception as e:
        error_msg = str(e).lower()
        fallback_errors = (
            '429',
            'rate limit',
            'rate_limit',
            'model_not_found',
            '404',
            'model does not exist',
            'model not found',
            'access to the model is unavailable',
            'tool_use_failed',
            'tool call validation failed',
            'tool choice is none',
        )
        matched_indicator = next(
            (error_indicator for error_indicator in fallback_errors if error_indicator in error_msg),
            None,
        )
        if matched_indicator is not None:
            logger.warning(
                "Groq primary call failed; switching to Gemini fallback "
                "reason=%s exception_type=%s exception_message=%s",
                matched_indicator,
                type(e).__name__,
                _safe_exception_message(e),
            )
            try:
                fallback_llm = get_fallback_llm()
                fallback_chain = chain_builder(fallback_llm)
                # Sanitize messages: Gemini rejects empty HumanMessages
                clean_args = _sanitize_messages(args)
                return fallback_chain.invoke(*clean_args, **kwargs)
            except Exception as fallback_e:
                logger.error(
                    "Gemini fallback failed exception_type=%s exception_message=%s",
                    type(fallback_e).__name__,
                    _safe_exception_message(fallback_e),
                )
                raise fallback_e from e
        logger.error(
            "Primary LLM failed with non-rate-limit error "
            "exception_type=%s exception_message=%s",
            type(e).__name__,
            _safe_exception_message(e),
        )
        raise e

