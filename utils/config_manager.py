"""
utils/config_manager.py — Gestor de Configuracion del Motor de IA

Funciones para:
- Probar la conexion con los distintos backends (Gemini, Ollama, OpenAI)
- Guardar la configuracion en el archivo .env
- Listar los modelos disponibles en Ollama
"""

import os
import time
import re
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
ENV_PATH = BASE_DIR / ".env"


def save_config_to_env(backend: str, model: str, api_key: str = "", base_url: str = "") -> bool:
    """
    Escribe la configuracion del LLM en el archivo .env.
    Retorna True si tuvo exito.
    """
    try:
        # Leer el .env actual como texto
        content = ENV_PATH.read_text(encoding="utf-8")
        
        def replace_or_append(text: str, key: str, value: str) -> str:
            """Reemplaza el valor de una clave en el texto .env, o la agrega si no existe."""
            pattern = rf"^{re.escape(key)}=.*$"
            new_line = f"{key}={value}"
            if re.search(pattern, text, re.MULTILINE):
                return re.sub(pattern, new_line, text, flags=re.MULTILINE)
            else:
                return text + f"\n{new_line}"
        
        content = replace_or_append(content, "LLM_BACKEND", backend)
        
        if backend == "gemini":
            content = replace_or_append(content, "GEMINI_MODEL", model)
            if api_key:
                content = replace_or_append(content, "GEMINI_API_KEY", api_key)
        elif backend == "ollama":
            content = replace_or_append(content, "OLLAMA_MODEL", model)
            if base_url:
                content = replace_or_append(content, "OLLAMA_BASE_URL", base_url)
        elif backend == "openai":
            content = replace_or_append(content, "OPENAI_MODEL", model)
            if api_key:
                content = replace_or_append(content, "OPENAI_API_KEY", api_key)
        elif backend == "anthropic":
            content = replace_or_append(content, "ANTHROPIC_MODEL", model)
            if api_key:
                content = replace_or_append(content, "ANTHROPIC_API_KEY", api_key)
        
        ENV_PATH.write_text(content, encoding="utf-8")
        return True
    except Exception as e:
        print(f"[config_manager] Error guardando .env: {e}")
        return False


def list_ollama_models(base_url: str = "http://localhost:11434") -> list[str]:
    """
    Consulta el servidor Ollama y retorna la lista de modelos instalados.
    """
    try:
        import urllib.request, json
        url = base_url.rstrip("/") + "/api/tags"
        with urllib.request.urlopen(url, timeout=3) as r:
            data = json.loads(r.read())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def test_connection(
    backend: str,
    model: str,
    api_key: str = "",
    base_url: str = "http://localhost:11434"
) -> dict:
    """
    Prueba la conexion con el backend especificado.
    Retorna un dict: {status, message, latency_ms, models}
      status: 'ok' | 'quota_error' | 'auth_error' | 'not_found' | 'error'
    """
    start = time.time()
    
    # ── GEMINI ────────────────────────────────────────────────────────────────
    if backend == "gemini":
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            m = genai.GenerativeModel(model)
            m.generate_content("di ok")
            latency_ms = int((time.time() - start) * 1000)
            return {
                "status": "success",
                "message": f"Conexion exitosa con {model}. Latencia: {latency_ms}ms.",
                "latency_ms": latency_ms,
                "models": [model]
            }
        except Exception as e:
            err = str(e)
            latency_ms = int((time.time() - start) * 1000)
            if "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower():
                retry_match = re.search(r"retry.*?(\d+)s", err, re.IGNORECASE)
                retry_in = retry_match.group(1) + "s" if retry_match else "unos minutos"
                # Obtener el modelo real del error
                model_match = re.search(r"model: ([\w\-\.]+)", err)
                model_real = model_match.group(1) if model_match else model
                return {
                    "status": "quota_error",
                    "message": f"Cuota agotada para '{model_real}'. Reintentá en {retry_in}.",
                    "latency_ms": latency_ms,
                    "models": []
                }
            elif "403" in err or "API_KEY_INVALID" in err or "permission" in err.lower():
                return {
                    "status": "auth_error",
                    "message": "API Key invalida o sin permisos para este modelo.",
                    "latency_ms": latency_ms,
                    "models": []
                }
            elif "404" in err or "NOT_FOUND" in err:
                return {
                    "status": "not_found",
                    "message": f"Modelo '{model}' no encontrado. Verifica el nombre en Google AI Studio.",
                    "latency_ms": latency_ms,
                    "models": []
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error: {err[:200]}",
                    "latency_ms": latency_ms,
                    "models": []
                }
    
    # ── OLLAMA ────────────────────────────────────────────────────────────────
    elif backend == "ollama":
        try:
            models = list_ollama_models(base_url)
            if not models:
                # Servidor responde pero sin modelos
                return {
                    "status": "success",
                    "message": f"Ollama conectado pero sin modelos instalados. Ejecuta: ollama pull {model or 'qwen2.5:7b'}",
                    "latency_ms": int((time.time() - start) * 1000),
                    "models": []
                }
            # Hacer un ping real con el modelo
            from langchain_community.chat_models import ChatOllama
            llm = ChatOllama(model=model, base_url=base_url, temperature=0)
            llm.invoke("di ok")
            latency_ms = int((time.time() - start) * 1000)
            return {
                "status": "success",
                "message": f"Ollama ok. Modelo '{model}' respondio en {latency_ms}ms.",
                "latency_ms": latency_ms,
                "models": models
            }
        except Exception as e:
            err = str(e)
            latency_ms = int((time.time() - start) * 1000)
            if "connection" in err.lower() or "refused" in err.lower() or "connect" in err.lower():
                return {
                    "status": "error",
                    "message": "No se puede conectar a Ollama. Asegurate que este corriendo (ollama serve).",
                    "latency_ms": latency_ms,
                    "models": []
                }
            return {
                "status": "error",
                "message": f"Error Ollama: {err[:200]}",
                "latency_ms": latency_ms,
                "models": []
            }

    # ── OPENAI ────────────────────────────────────────────────────────────────
    elif backend == "openai":
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model=model, api_key=api_key, temperature=0)
            llm.invoke("di ok")
            latency_ms = int((time.time() - start) * 1000)
            return {
                "status": "success",
                "message": f"OpenAI ok. Modelo '{model}' respondio en {latency_ms}ms.",
                "latency_ms": latency_ms,
                "models": [model]
            }
        except Exception as e:
            err = str(e)
            latency_ms = int((time.time() - start) * 1000)
            if "401" in err or "invalid_api_key" in err.lower() or "Incorrect API key" in err:
                return {"status": "auth_error", "message": "API Key de OpenAI invalida.", "latency_ms": latency_ms, "models": []}
            elif "429" in err or "quota" in err.lower():
                return {"status": "quota_error", "message": "Cuota de OpenAI agotada.", "latency_ms": latency_ms, "models": []}
            return {"status": "error", "message": f"Error OpenAI: {err[:200]}", "latency_ms": latency_ms, "models": []}
    
    # ── ANTHROPIC (CLAUDE) ───────────────────────────────────────────────────
    elif backend == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
            llm = ChatAnthropic(model=model, api_key=api_key, temperature=0)
            llm.invoke("di ok")
            latency_ms = int((time.time() - start) * 1000)
            return {
                "status": "success",
                "message": f"Anthropic ok. Modelo '{model}' respondio en {latency_ms}ms.",
                "latency_ms": latency_ms,
                "models": [model]
            }
        except Exception as e:
            err = str(e)
            latency_ms = int((time.time() - start) * 1000)
            if "401" in err or "authentication" in err.lower():
                return {"status": "auth_error", "message": "API Key de Anthropic invalida.", "latency_ms": latency_ms, "models": []}
            return {"status": "error", "message": f"Error Anthropic: {err[:200]}", "latency_ms": latency_ms, "models": []}
    
    return {"status": "error", "message": f"Backend desconocido: {backend}", "latency_ms": 0, "models": []}


def get_current_config() -> dict:
    """Lee la configuracion actual del .env y la retorna como dict."""
    load_dotenv(ENV_PATH, override=True)
    return {
        "backend": os.getenv("LLM_BACKEND", "gemini"),
        "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o"),
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "ollama_model": os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "anthropic_model": os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620"),
    }
