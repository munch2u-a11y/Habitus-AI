import json
import pytest
from pathlib import Path
from habitus_ai.app import create_handler_class, fetch_ollama_models, main, AppRequestHandler
from habitus_ai import HabitusAI

def test_fetch_ollama_models_fallback():
    models = fetch_ollama_models("http://127.0.0.1:99999") # invalid port to test fallback
    assert len(models) > 0
    assert "granite4.1:8b" in models

def test_app_imports_and_handler(tmp_path):
    database_path = tmp_path / "test_app_mind.sqlite"
    handler_class = create_handler_class(database_path, "http://127.0.0.1:11434")
    assert issubclass(handler_class, AppRequestHandler)
    assert handler_class.database_path == database_path
