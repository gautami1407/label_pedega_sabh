import os
import toml

# Try to load from secrets.toml if available
try:
    secrets = toml.load("secrets.toml")
except Exception:
    try:
        # Try loading from parent directory if running from app.py context
        secrets = toml.load("cloud_rangers/project/backend/secrets.toml")
    except Exception:
        secrets = {"general": {}}

def get_api_key(service):
    """
    Retrieve API key for a service (gemini or usda).
    Prioritizes environment variables, then secrets.toml.
    """
    env_key = f"{service.upper()}_API_KEY"
    if os.environ.get(env_key):
        return os.environ.get(env_key)
    
    return secrets.get("general", {}).get(f"{service}_api_key")
