"""
config.py — API key loader
Priority order:
  1. Environment variables  (GEMINI_API_KEY, USDA_API_KEY)
  2. secrets.toml           (same directory as this file)
"""
import os
import toml

_HERE = os.path.dirname(os.path.abspath(__file__))
_SECRETS_PATH = os.path.join(_HERE, "secrets.toml")

def _load_secrets():
    try:
        return toml.load(_SECRETS_PATH)
    except Exception:
        return {"general": {}}

_secrets = _load_secrets()

def get_api_key(service: str) -> str:
    """
    Return the API key for `service` (e.g. 'gemini', 'usda').
    Checks env var first, then secrets.toml.
    """
    env_key = f"{service.upper()}_API_KEY"
    val = os.environ.get(env_key, "").strip()
    if val:
        return val
    return _secrets.get("general", {}).get(f"{service}_api_key", "")
