#!/usr/bin/env bash
# KAVAL / AI-5 — serve a free, keyless, open-weight LLM for the analyst to plan with.
#
# llama.cpp's llama-server speaks the OpenAI /chat/completions API with tool calling
# (--jinja uses the model's own chat template, which is what makes tools work).
# The analyst picks it up automatically on 127.0.0.1:8078 when no API key is set.
#
#   Model:  Qwen2.5-7B-Instruct, Q4_K_M GGUF (Apache-2.0), ~4.7 GB
#   Binary: llama.cpp release build, CPU (ggml-org/llama.cpp, MIT)
#
# Override with LLAMA_SERVER=/path/to/llama-server, KAVAL_GGUF=/path/to/model.gguf,
# KAVAL_LLM_PORT, KAVAL_LLM_CTX, KAVAL_LLM_THREADS.
set -euo pipefail
DIR="${KAVAL_LLM_DIR:-$HOME/.local/share/kaval-llm}"
SERVER="${LLAMA_SERVER:-$(ls "$DIR"/llama-b*/llama-server 2>/dev/null | sort -V | tail -1)}"
MODEL="${KAVAL_GGUF:-$DIR/qwen2.5-7b-instruct-q4_k_m.gguf}"
[ -x "$SERVER" ] || { echo "llama-server not found in $DIR (see docs/team/10_API_ANALYST.md)"; exit 1; }
[ -f "$MODEL" ]  || { echo "model not found: $MODEL"; exit 1; }
exec "$SERVER" -m "$MODEL" --jinja --host 127.0.0.1 --port "${KAVAL_LLM_PORT:-8078}" \
  -c "${KAVAL_LLM_CTX:-16384}" -t "${KAVAL_LLM_THREADS:-6}" \
  --parallel 1 --alias "$(basename "$MODEL" .gguf)"
