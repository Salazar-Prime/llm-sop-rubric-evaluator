"""
OpenAI API utility functions for processing statements of purpose.

Model compatibility
───────────────────
GPT-5.x and o-series (reasoning models)
  gpt-5.2, gpt-5.2-2025-12-11
  gpt-5.4, gpt-5.4-2026-03-05, gpt-5.4-mini, gpt-5.4-nano
  gpt-5.5, gpt-5.5-pro
  o1, o3, o3-mini, …
  → Use reasoning_effort (none/low/medium/high/xhigh).
  → Do NOT pass temperature, top_p, frequency_penalty, presence_penalty.

GPT-4.x and older (sampling models)
  gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo, …
  → Use temperature, top_p, frequency_penalty, presence_penalty.
  → reasoning_effort is not applicable.

max_tokens is deprecated for all models; use max_completion_tokens instead.
"""

from openai import OpenAI
import os
from dotenv import load_dotenv
import json

load_dotenv()


# ── Model family detection ────────────────────────────────────────────────────

def _is_reasoning_model(model: str) -> bool:
    """Return True for GPT-5.x and o-series models that use reasoning_effort."""
    m = model.lower()
    return m.startswith("gpt-5") or m.startswith("o1") or m.startswith("o3") or m.startswith("o4")


# ── Client ────────────────────────────────────────────────────────────────────

def initialize_openai_client():
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ── Prompt loading ────────────────────────────────────────────────────────────

def load_system_prompt(prompt_file=None, program_name=None, institution=None):
    """Load system prompt from file and substitute {program_name}/{institution} placeholders."""
    if prompt_file is None:
        prompt_file = "systemPromptv2.txt"
    try:
        with open(prompt_file, "r") as f:
            text = f.read().strip()
        # Use plain replace instead of .format() so the literal { } characters
        # inside the rubric JSON body are not mistaken for format placeholders.
        if program_name:
            text = text.replace("{program_name}", program_name)
        if institution:
            text = text.replace("{institution}", institution)
        return text
    except FileNotFoundError:
        print(f"System prompt file {prompt_file} not found.")
        return "You are a helpful assistant."


# ── API call ──────────────────────────────────────────────────────────────────

def getResponse(sop_text, json_schema, model="gpt-4o-mini", prompt_file=None,
                program_name=None, institution=None, reasoning_effort="low"):
    """
    Get an OpenAI structured response for a statement of purpose.

    Parameters
    ----------
    sop_text : str
        Cleaned statement of purpose text.
    json_schema : dict
        JSON schema dict loaded from jsonSchema.json.
    model : str
        OpenAI model ID. GPT-5.x / o-series models use reasoning_effort;
        GPT-4.x and older use temperature/top_p sampling params.
    reasoning_effort : str
        For reasoning models only — none | low | medium | high | xhigh.
        "low" is sufficient for rubric scoring and minimises cost/latency.

    Returns
    -------
    dict with keys ``response`` (parsed JSON) and ``usage_log`` (token counts).
    Raises on API error rather than returning a silent error dict.
    """
    client = initialize_openai_client()
    system_prompt = load_system_prompt(prompt_file, program_name=program_name,
                                       institution=institution)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": sop_text},
    ]

    # Build call kwargs based on model family
    kwargs = dict(
        model=model,
        messages=messages,
        response_format={"type": "json_schema", "json_schema": json_schema},
        max_completion_tokens=1000,   # max_tokens is deprecated
    )

    if _is_reasoning_model(model):
        # GPT-5.x / o-series: temperature and sampling params are not supported
        kwargs["reasoning_effort"] = reasoning_effort
    else:
        # GPT-4.x and older: standard sampling params
        kwargs["temperature"]         = 0.1
        kwargs["top_p"]               = 1
        kwargs["frequency_penalty"]   = 0
        kwargs["presence_penalty"]    = 0

    response = client.chat.completions.create(**kwargs)

    usage_dict = {
        "prompt_tokens":     response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens":      response.usage.total_tokens,
    }

    response_json = json.loads(response.choices[0].message.content)
    return {
        "response":  response_json,
        "usage_log": usage_dict,
    }
