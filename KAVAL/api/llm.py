"""
KAVAL / AI-5 — which LLM plans over the analyst's tools, and the loop that runs it.

The analyst's tools, dispatch and citations live in analyst.py. This module only
answers two questions: *which model is available right now*, and *how do we talk
to it*. Two wire formats cover every provider we support:

  anthropic       the Messages API (ANTHROPIC_API_KEY)
  openai_compat   OpenAI-style /chat/completions with `tools` — spoken by Google's
                  Gemini API (free tier), Groq, OpenRouter, and a local llama.cpp
                  `llama-server --jinja`. One loop serves all of them.

Fallback chain. Every available provider is tried in this order, and within a
provider every listed model, until one answers; if all fail, the offline keyword
planner answers and says why (all overridable, nothing hard-codes a key):

  1. KAVAL_LLM_PROVIDER = anthropic | gemini | groq | openrouter | local | offline
     pins the chain to one provider
  2. ANTHROPIC_API_KEY                      -> anthropic
  3. GEMINI_API_KEY or GOOGLE_API_KEY       -> gemini free tier: gemini-3.8-flash,
                                               then gemini-3-flash-preview, then
                                               gemini-flash-lite-latest
  4. GROQ_API_KEY                           -> groq
  5. OPENROUTER_API_KEY                     -> openrouter (a ':free' model)
  6. KAVAL_LLM_BASE_URL                     -> any OpenAI-compatible server
  7. a llama-server answering on KAVAL_LOCAL_LLM_URL (default 127.0.0.1:8078)
                                            -> local open-weight model, no key
  8. all of the above failed or absent      -> the offline keyword planner

KAVAL_LLM_MODEL is tried first for whichever provider is reached. Keys are read
from the environment at call time and never logged, echoed or stored.
"""

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx

ANTHROPIC_MODEL = "claude-sonnet-5-5"

# Hosted OpenAI-compatible endpoints. Each lists its free-tier models in the order
# to try: a model that is retired, rate-limited or overloaded (404/429/5xx) falls
# through to the next. KAVAL_LLM_MODEL, if set, is tried first. Verified for tool
# calling on 2026-10-01: gemini-3.8-flash, gemini-3-flash-preview,
# gemini-flash-lite-latest (gemini-2.5-flash is closed to new users).
HOSTED = {
    "gemini": {"env": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
               "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
               "models": ["gemini-3.8-flash", "gemini-3-flash-preview",
                          "gemini-flash-lite-latest"]},
    "groq": {"env": ("GROQ_API_KEY",),
             "base_url": "https://api.groq.com/openai/v1",
             "models": ["llama-3.3-70b-versatile"]},
    "openrouter": {"env": ("OPENROUTER_API_KEY",),
                   "base_url": "https://openrouter.ai/api/v1",
                   "models": ["meta-llama/llama-3.3-70b-instruct:free"]},
}
LOCAL_URL_DEFAULT = "http://127.0.0.1:8078/v1"

# A local 7B model on CPU has a small context and reads slowly; hosted models get
# more of each tool result. Rows beyond this are cut, and the model is told so.
PAYLOAD_CHARS = {"local": 6000, "default": 20000}


@dataclass(frozen=True)
class Provider:
    name: str            # anthropic | gemini | groq | openrouter | custom | local
    kind: str            # anthropic | openai_compat
    model: str
    base_url: str | None = None
    api_key_env: str | None = None

    @property
    def label(self) -> str:
        return f"{self.name}:{self.model}"


_local_probe: dict[str, Any] = {"t": 0.0, "model": None, "url": None}


def _probe_local(url: str) -> str | None:
    """Model id served by a local OpenAI-compatible server, cached for 20 s."""
    now = time.time()
    if _local_probe["url"] == url and now - _local_probe["t"] < 20:
        return _local_probe["model"]
    model = None
    try:
        r = httpx.get(f"{url}/models", timeout=1.5)
        if r.status_code == 200:
            data = r.json().get("data") or []
            model = data[0]["id"] if data else "local"
    except (httpx.HTTPError, ValueError, KeyError, IndexError):
        model = None
    _local_probe.update(t=now, model=model, url=url)
    return model


def _hosted(name: str) -> list[Provider]:
    """Every model to try for a hosted provider whose key is set, in order."""
    cfg = HOSTED[name]
    env = next((e for e in cfg["env"] if os.environ.get(e)), None)
    if not env:
        return []
    models = list(cfg["models"])
    if os.environ.get("KAVAL_LLM_MODEL"):
        models.insert(0, os.environ["KAVAL_LLM_MODEL"])
    return [Provider(name, "openai_compat", m, cfg["base_url"], env)
            for m in dict.fromkeys(models)]


def _local() -> list[Provider]:
    url = os.environ.get("KAVAL_LOCAL_LLM_URL", LOCAL_URL_DEFAULT).rstrip("/")
    model = _probe_local(url)
    return [Provider("local", "openai_compat", model, url, None)] if model else []


def _anthropic() -> list[Provider]:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return []
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return []
    return [Provider("anthropic", "anthropic",
                     os.environ.get("KAVAL_LLM_MODEL", ANTHROPIC_MODEL))]


def _custom() -> list[Provider]:
    base = os.environ.get("KAVAL_LLM_BASE_URL")
    if not base:
        return []
    return [Provider("custom", "openai_compat",
                     os.environ.get("KAVAL_LLM_MODEL", "default"), base.rstrip("/"),
                     "KAVAL_LLM_API_KEY" if os.environ.get("KAVAL_LLM_API_KEY") else None)]


def candidates() -> list[Provider]:
    """
    Every LLM to try, in order; the analyst walks this list and falls through on
    failure, ending at the offline planner. Empty means offline only.
    KAVAL_LLM_PROVIDER pins one provider (its model list still falls through).
    """
    forced = (os.environ.get("KAVAL_LLM_PROVIDER")
              or os.environ.get("KAVAL_ANALYST_PLANNER") or "").strip().lower()
    if forced == "offline":
        return []
    if forced in HOSTED:
        return _hosted(forced)
    if forced == "local":
        return _local()
    if forced == "anthropic":
        return _anthropic()
    chain = _anthropic()
    for name in HOSTED:
        chain += _hosted(name)
    return chain + _custom() + _local()


def resolve() -> Provider | None:
    """The first provider /analyst/query would try now (skipping models cooling
    down after a 429/503); None means offline."""
    c = [p for p in candidates() if not cooling_down(p)] or candidates()
    return c[0] if c else None


# Models that just refused for quota or overload (429/503) are skipped for a while,
# so each question does not spend two failed calls before reaching one that answers.
_COOLDOWN_S = 300
_cooling: dict[str, float] = {}


def cooling_down(p: "Provider") -> bool:
    return time.time() < _cooling.get(p.label, 0.0)


def mark_overloaded(p: "Provider") -> None:
    _cooling[p.label] = time.time() + _COOLDOWN_S


class ProviderError(RuntimeError):
    """The provider failed (network, auth, quota, overload). The caller moves on to
    the next candidate, and finally to the offline planner."""


def openai_tools(tools: list[dict]) -> list[dict]:
    """Anthropic-style tool specs -> OpenAI `tools` entries. Same names, same schema."""
    return [{"type": "function",
             "function": {"name": t["name"], "description": t["description"],
                          "parameters": t["input_schema"]}} for t in tools]


def run_openai_compat(p: Provider, system: str, question: str, tools: list[dict],
                      execute: Callable[[str, dict], str], max_turns: int) -> str | None:
    """
    Standard tool loop. `execute(name, args)` runs one tool and returns the JSON
    string handed back to the model. Returns the final text, or None if the model
    never stopped calling tools within max_turns.
    """
    headers = {"Content-Type": "application/json"}
    if p.api_key_env:
        headers["Authorization"] = f"Bearer {os.environ[p.api_key_env]}"
    limit = PAYLOAD_CHARS["local" if p.name == "local" else "default"]
    # A CPU-hosted 7B model can take minutes over a long tool result.
    timeout = httpx.Timeout(900.0 if p.name == "local" else 120.0, connect=10.0)
    messages: list[dict] = [{"role": "system", "content": system},
                            {"role": "user", "content": question}]
    spec = openai_tools(tools)

    with httpx.Client(timeout=timeout) as client:
        for _ in range(max_turns):
            # Capped: an uncapped small model can ramble for minutes on a CPU. The
            # system prompt asks for short answers anyway.
            body = {"model": p.model, "messages": messages, "tools": spec,
                    "tool_choice": "auto", "temperature": 0, "max_tokens": 800}
            try:
                r = client.post(f"{p.base_url}/chat/completions", headers=headers,
                                json=body)
            except httpx.HTTPError as exc:
                raise ProviderError(f"{p.label}: {type(exc).__name__}") from exc
            if r.status_code in (429, 503):
                mark_overloaded(p)
            if r.status_code != 200:
                # Never echo the request: it carries the key in a header.
                raise ProviderError(f"{p.label}: HTTP {r.status_code} "
                                    f"{r.text[:200].strip()}")
            msg = (r.json().get("choices") or [{}])[0].get("message") or {}
            calls = msg.get("tool_calls") or []
            if not calls:
                return (msg.get("content") or "").strip()

            messages.append({"role": "assistant", "content": msg.get("content") or "",
                             "tool_calls": calls})
            for c in calls:
                fn = c.get("function") or {}
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                    if not isinstance(args, dict):
                        args = {}
                except json.JSONDecodeError:
                    args = {}
                out = execute(fn.get("name", ""), args)
                if len(out) > limit:
                    out = out[:limit] + ' … [truncated: ask a narrower question]'
                messages.append({"role": "tool", "tool_call_id": c.get("id", ""),
                                 "name": fn.get("name", ""), "content": out})
    return None
