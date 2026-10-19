#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
export OLLAMA_HOST=127.0.0.1:11434

if ! command -v ollama >/dev/null 2>&1 || ! command -v opencode >/dev/null 2>&1; then
  echo 'Se necesitan ollama y opencode en PATH.' >&2
  exit 1
fi

for model_file in "$project_dir/models/Modelfile.llama31" "$project_dir/models/Modelfile.phi4-mini"; do
  gguf_path="$(sed -n 's/^FROM //p' "$model_file")"
  if [[ ! -r "$gguf_path" ]]; then
    echo "No se puede leer el GGUF: $gguf_path" >&2
    exit 1
  fi
done

if ! ollama list >/dev/null 2>&1; then
  log_file="$(mktemp "${TMPDIR:-/tmp}/opencode-ollama.XXXXXX.log")"
  echo "Iniciando Ollama. Registro: $log_file"
  OLLAMA_HOST=127.0.0.1:11434 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 \
    nohup ollama serve >"$log_file" 2>&1 </dev/null &
  for attempt in {1..30}; do
    if ollama list >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  if ! ollama list >/dev/null 2>&1; then
    echo "Ollama no inició. Revisa $log_file" >&2
    exit 1
  fi
fi

if ! ollama show local-llama31-8b >/dev/null 2>&1; then
  echo 'Importando Llama 3.1 8B a Ollama (puede tardar unos minutos)...'
  ollama create local-llama31-8b -f "$project_dir/models/Modelfile.llama31"
fi
if ! ollama show local-phi4-mini >/dev/null 2>&1; then
  echo 'Importando Phi-4 mini a Ollama (puede tardar unos minutos)...'
  ollama create local-phi4-mini -f "$project_dir/models/Modelfile.phi4-mini"
fi

if [[ "${1:-}" == '--setup-only' ]]; then
  echo 'Modelos listos. Ejecuta opencode en este directorio.'
  exit 0
fi

exec opencode "$@"
