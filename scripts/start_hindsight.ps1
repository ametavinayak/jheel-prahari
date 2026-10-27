# Starts the Hindsight memory server (embedded Postgres, ONNX embeddings) with its LLM on the office GPU's Ollama.
# Override OLLAMA_HOST to point somewhere else, e.g. http://127.0.0.1:11434 on a machine with its own Ollama.
$root = Split-Path -Parent $PSScriptRoot
$ollama = if ($env:OLLAMA_HOST) { $env:OLLAMA_HOST } else { "http://100.101.142.24:11434" }
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
$env:HINDSIGHT_API_LLM_PROVIDER = "ollama"
$env:HINDSIGHT_API_LLM_BASE_URL = "$ollama/v1"
$env:HINDSIGHT_API_LLM_MODEL = "qwen3:8b"
$env:HINDSIGHT_API_EMBEDDINGS_PROVIDER = "onnx"
$env:HINDSIGHT_API_RERANKER_PROVIDER = "onnx"
# One GPU shared with other work: never more than one LLM call at a time, no background consolidation.
$env:HINDSIGHT_API_LLM_MAX_CONCURRENT = "1"
$env:HINDSIGHT_API_CONSOLIDATION_LLM_MAX_CONCURRENT = "1"
$env:HINDSIGHT_API_ENABLE_AUTO_CONSOLIDATION = "false"
$env:HINDSIGHT_API_LLM_MAX_RETRIES = "2"
& "$root\.hs-venv\Scripts\hindsight-api.exe"
