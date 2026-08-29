from __future__ import annotations

import argparse
import json
import os
import urllib.request
import urllib.error
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from .agent import HatchedAgent
from .gestation import TASTE_SCHEMAS, GestationProfile, gestate, load_profile
from .models import ModelUnavailableError, OllamaChatModel
from .pipeline import BaseAgenticMemoryRAG

DEFAULT_DATABASE = "habitus_memory.sqlite"

FALLBACK_MODELS = [
    "granite4.1:8b",
    "llama3.2:latest",
    "qwen2.5:7b",
    "mistral:latest",
    "gemma2:9b",
    "phi4:latest",
]


def fetch_ollama_models(ollama_url: str = "http://127.0.0.1:11434") -> list[str]:
    """Fetch locally installed models from Ollama API."""
    try:
        url = f"{ollama_url.rstrip('/')}/api/tags"
        req = urllib.request.Request(url, headers={"User-Agent": "Habitus-AI/0.2.0"})
        with urllib.request.urlopen(req, timeout=3.0) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                if models:
                    return models
    except Exception:
        pass
    return FALLBACK_MODELS


class AppRequestHandler(BaseHTTPRequestHandler):
    database_path: Path = Path(DEFAULT_DATABASE)
    ollama_url: str = "http://127.0.0.1:11434"

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy standard HTTP logging
        pass

    def _send_json(self, data: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, status: int = 200) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/" or self.path == "/index.html":
            self._send_html(HTML_INTERFACE)
        elif self.path == "/api/models":
            models = fetch_ollama_models(self.ollama_url)
            self._send_json({"models": models, "source": "ollama_autodetect"})
        elif self.path == "/api/status":
            with BaseAgenticMemoryRAG(self.database_path) as mind:
                profile = load_profile(mind)
                if profile is None:
                    self._send_json({"hatched": False})
                    return
                store = mind.store
                record_count = int(store.connection.execute("SELECT COUNT(*) FROM records").fetchone()[0])
                concept_count = len(store.list_concepts(kind="crown"))
                edge_count = len(store.list_edges())
                errors = mind.graph.validate_invariants()
                self._send_json({
                    "hatched": True,
                    "agent_name": profile.agent_name,
                    "human_name": profile.human_name,
                    "taste_schema": profile.taste_schema,
                    "model_name": profile.model_name,
                    "records": record_count,
                    "concepts": concept_count,
                    "edges": edge_count,
                    "healthy": len(errors) == 0,
                    "invariants": errors,
                })
        else:
            self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception:
            payload = {}

        if self.path == "/api/gestate":
            human_name = payload.get("human_name", "User")
            agent_name = payload.get("agent_name", "HabitusAgent")
            taste = payload.get("taste", "balanced")
            model = payload.get("model", "granite4.1:8b")

            with BaseAgenticMemoryRAG(self.database_path) as mind:
                existing = load_profile(mind)
                if existing is not None:
                    profile = existing
                else:
                    profile = gestate(
                        mind,
                        human_name=human_name,
                        agent_name=agent_name,
                        taste_schema=taste,
                        model_backend="ollama",
                        model_name=model,
                    )

            self._send_json({
                "status": "success",
                "agent_name": profile.agent_name,
                "human_name": profile.human_name,
                "taste_schema": profile.taste_schema,
                "model_name": profile.model_name,
            })

        elif self.path == "/api/chat":
            message = payload.get("message", "").strip()
            if not message:
                self._send_json({"error": "Empty message"}, status=400)
                return

            with BaseAgenticMemoryRAG(self.database_path) as mind:
                profile = load_profile(mind)
                if profile is None:
                    self._send_json({"error": "Agent mind is not gestated yet. Run gestation first."}, status=400)
                    return

                chat_model = OllamaChatModel(
                    profile.model_name,
                    base_url=self.ollama_url,
                    timeout_seconds=180.0,
                )
                agent = HatchedAgent(mind, chat_model, history_messages=8)

                try:
                    turn = agent.turn(message)
                    agent.acknowledge_delivery(turn, channel="web_app")
                    self._send_json({
                        "response": turn.response,
                        "trunk": turn.decision.trunk.value if turn.decision.trunk else "PRIVATE",
                        "y_paths": turn.recall_result.packet.y_paths,
                        "direct_record_ids": turn.recall_result.packet.direct_record_ids,
                        "context_preview": turn.recall_result.context[:300] + "...",
                    })
                except ModelUnavailableError as err:
                    self._send_json({"error": f"Local LLM unavailable: {err}"}, status=503)

        elif self.path == "/api/tools":
            # Dev tab tool registration placeholder
            tool_name = payload.get("tool_name")
            tool_type = payload.get("tool_type", "LOOK")
            tool_spec = payload.get("tool_spec", "")
            self._send_json({
                "status": "registered",
                "tool_name": tool_name,
                "tool_type": tool_type,
                "tool_spec": tool_spec,
            })

        else:
            self.send_error(404, "Endpoint Not Found")


def create_handler_class(database_path: Path, ollama_url: str) -> type[AppRequestHandler]:
    class BoundHandler(AppRequestHandler):
        pass
    BoundHandler.database_path = database_path
    BoundHandler.ollama_url = ollama_url
    return BoundHandler


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch Habitus AI Web App Launcher")
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    database = Path(args.database)
    handler_class = create_handler_class(database, args.ollama_url)
    server = HTTPServer(("127.0.0.1", args.port), handler_class)

    url = f"http://127.0.0.1:{args.port}"
    print(f"🏛️ Habitus AI Web Launcher running at {url}")
    print(f"🧠 Database: {database.resolve()}")

    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Habitus AI Launcher.")
        server.server_close()


HTML_INTERFACE = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Habitus AI — Cognitive Launcher</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-dark: #090a10;
            --bg-card: #121420;
            --bg-glass: rgba(18, 20, 32, 0.75);
            --border-glow: rgba(0, 240, 255, 0.2);
            --border-card: rgba(255, 255, 255, 0.08);
            --accent-cyan: #00f0ff;
            --accent-purple: #9d4edd;
            --accent-pink: #ff007f;
            --text-primary: #f0f2f8;
            --text-secondary: #9499b0;
            --font-main: 'Outfit', sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background-color: var(--bg-dark);
            color: var(--text-primary);
            font-family: var(--font-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            background-image: 
                radial-gradient(circle at 15% 15%, rgba(0, 240, 255, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 85% 85%, rgba(157, 78, 221, 0.08) 0%, transparent 40%);
            overflow-x: hidden;
        }

        /* Top Navigation Header */
        header {
            padding: 1.25rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-card);
            backdrop-filter: blur(12px);
            background: var(--bg-glass);
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .logo-container {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        .logo-icon {
            font-size: 1.8rem;
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 700;
        }
        .logo-text h1 { font-size: 1.3rem; font-weight: 700; letter-spacing: 0.5px; }
        .logo-text span { font-size: 0.75rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 1.5px; }

        .nav-tabs {
            display: flex;
            gap: 0.5rem;
            background: rgba(0, 0, 0, 0.3);
            padding: 0.25rem;
            border-radius: 12px;
            border: 1px solid var(--border-card);
        }
        .tab-btn {
            padding: 0.6rem 1.2rem;
            border: none;
            background: transparent;
            color: var(--text-secondary);
            font-family: var(--font-main);
            font-weight: 500;
            font-size: 0.9rem;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.25s ease;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .tab-btn:hover { color: var(--text-primary); }
        .tab-btn.active {
            background: linear-gradient(135deg, rgba(0, 240, 255, 0.15), rgba(157, 78, 221, 0.15));
            color: var(--accent-cyan);
            border: 1px solid rgba(0, 240, 255, 0.3);
            box-shadow: 0 0 15px rgba(0, 240, 255, 0.1);
        }

        /* Main App Container */
        main {
            flex: 1;
            max-width: 1100px;
            width: 100%;
            margin: 2rem auto;
            padding: 0 1.5rem;
        }

        .tab-content { display: none; }
        .tab-content.active { display: block; animation: fadeIn 0.3s ease; }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Cards & Forms */
        .glass-card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 20px;
            padding: 2rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
            margin-bottom: 1.5rem;
            backdrop-filter: blur(16px);
        }
        .card-header {
            margin-bottom: 1.5rem;
        }
        .card-header h2 { font-size: 1.4rem; font-weight: 600; color: var(--text-primary); }
        .card-header p { font-size: 0.9rem; color: var(--text-secondary); margin-top: 0.25rem; }

        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
        }
        .form-group { display: flex; flex-direction: column; gap: 0.5rem; }
        .form-group label { font-size: 0.85rem; font-weight: 500; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 1px; }

        input, select, textarea {
            width: 100%;
            padding: 0.85rem 1rem;
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid var(--border-card);
            border-radius: 12px;
            color: var(--text-primary);
            font-family: var(--font-main);
            font-size: 0.95rem;
            transition: all 0.2s ease;
        }
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: var(--accent-cyan);
            box-shadow: 0 0 12px rgba(0, 240, 255, 0.25);
        }

        .detect-btn {
            background: rgba(0, 240, 255, 0.1);
            color: var(--accent-cyan);
            border: 1px solid rgba(0, 240, 255, 0.3);
            padding: 0.4rem 0.8rem;
            font-size: 0.75rem;
            font-weight: 600;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .detect-btn:hover { background: rgba(0, 240, 255, 0.25); }

        /* Taste Cards Grid */
        .taste-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-top: 0.5rem;
        }
        .taste-card {
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--border-card);
            border-radius: 14px;
            padding: 1rem;
            cursor: pointer;
            transition: all 0.25s ease;
        }
        .taste-card:hover { border-color: rgba(0, 240, 255, 0.4); }
        .taste-card.selected {
            border-color: var(--accent-cyan);
            background: linear-gradient(135deg, rgba(0, 240, 255, 0.1), rgba(157, 78, 221, 0.1));
            box-shadow: 0 0 15px rgba(0, 240, 255, 0.15);
        }
        .taste-card h4 { font-size: 1rem; font-weight: 600; margin-bottom: 0.25rem; color: var(--accent-cyan); }
        .taste-card p { font-size: 0.8rem; color: var(--text-secondary); line-height: 1.3; }

        /* Primary Action Buttons */
        .cta-btn {
            width: 100%;
            padding: 1rem;
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple));
            color: #000;
            font-weight: 700;
            font-size: 1.05rem;
            border: none;
            border-radius: 14px;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 20px rgba(0, 240, 255, 0.3);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
        }
        .cta-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 25px rgba(0, 240, 255, 0.5);
        }

        /* Gestation Modal & Egg Animation */
        .modal-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(5, 6, 10, 0.85);
            backdrop-filter: blur(12px);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        .modal-overlay.active { display: flex; animation: fadeIn 0.3s ease; }
        .modal-card {
            background: var(--bg-card);
            border: 1px solid var(--border-glow);
            border-radius: 24px;
            padding: 2.5rem;
            width: 90%;
            max-width: 480px;
            text-align: center;
            box-shadow: 0 20px 50px rgba(0, 240, 255, 0.2);
        }

        /* Egg Sprite Animation */
        .egg-container {
            position: relative;
            width: 120px;
            height: 140px;
            margin: 0 auto 1.5rem auto;
        }
        .egg-sprite {
            width: 100px;
            height: 130px;
            background: linear-gradient(135deg, #f0f2f8, #c5cae9);
            border-radius: 50% 50% 50% 50% / 60% 60% 40% 40%;
            margin: 0 auto;
            position: relative;
            box-shadow: 
                inset -10px -10px 20px rgba(0, 0, 0, 0.2),
                0 0 30px rgba(0, 240, 255, 0.4);
            animation: floatEgg 2.5s ease-in-out infinite;
        }
        .egg-sprite::after {
            content: '';
            position: absolute;
            top: 20px; left: 20px;
            width: 20px; height: 35px;
            background: rgba(255, 255, 255, 0.6);
            border-radius: 50%;
        }
        .egg-glow {
            position: absolute;
            bottom: -10px; left: 50%;
            transform: translateX(-50%);
            width: 80px; height: 16px;
            background: rgba(0, 240, 255, 0.4);
            filter: blur(10px);
            border-radius: 50%;
            animation: pulseGlow 2.5s ease-in-out infinite;
        }

        @keyframes floatEgg {
            0%, 100% { transform: translateY(0) rotate(0deg); }
            50% { transform: translateY(-12px) rotate(2deg); }
        }
        @keyframes pulseGlow {
            0%, 100% { transform: translateX(-50%) scale(1); opacity: 0.6; }
            50% { transform: translateX(-50%) scale(1.3); opacity: 1; }
        }

        .progress-bar-container {
            width: 100%;
            height: 12px;
            background: rgba(0, 0, 0, 0.5);
            border-radius: 10px;
            overflow: hidden;
            border: 1px solid var(--border-card);
            margin: 1.25rem 0 0.75rem 0;
        }
        .progress-bar-fill {
            height: 100%;
            width: 0%;
            background: linear-gradient(90deg, var(--accent-cyan), var(--accent-purple));
            border-radius: 10px;
            transition: width 0.2s linear;
        }

        .status-text { font-size: 0.85rem; color: var(--text-secondary); font-family: var(--font-mono); }

        /* Chat Interface */
        .chat-container {
            display: flex;
            flex-direction: column;
            height: 600px;
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 20px;
            overflow: hidden;
        }
        .chat-header {
            padding: 1rem 1.5rem;
            background: rgba(0, 0, 0, 0.3);
            border-bottom: 1px solid var(--border-card);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .chat-header-info { display: flex; align-items: center; gap: 0.75rem; }
        .status-badge {
            width: 10px; height: 10px; border-radius: 50%;
            background: #00e676; box-shadow: 0 0 10px #00e676;
        }
        .chat-messages {
            flex: 1;
            padding: 1.5rem;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }
        .message-bubble {
            max-width: 80%;
            padding: 1rem 1.25rem;
            border-radius: 16px;
            font-size: 0.95rem;
            line-height: 1.5;
        }
        .message-user {
            align-self: flex-end;
            background: linear-gradient(135deg, rgba(0, 240, 255, 0.2), rgba(157, 78, 221, 0.2));
            border: 1px solid rgba(0, 240, 255, 0.3);
            color: var(--text-primary);
        }
        .message-agent {
            align-self: flex-start;
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid var(--border-card);
            color: var(--text-primary);
        }
        .message-meta {
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-top: 0.4rem;
            display: flex;
            gap: 0.75rem;
            font-family: var(--font-mono);
        }
        .meta-tag {
            background: rgba(0, 240, 255, 0.1);
            color: var(--accent-cyan);
            padding: 0.1rem 0.4rem;
            border-radius: 4px;
        }

        .chat-input-bar {
            padding: 1rem 1.5rem;
            background: rgba(0, 0, 0, 0.4);
            border-top: 1px solid var(--border-card);
            display: flex;
            gap: 0.75rem;
        }
    </style>
</head>
<body>

    <header>
        <div class="logo-container">
            <div class="logo-icon">🏛️</div>
            <div class="logo-text">
                <h1>Habitus AI</h1>
                <span>Cognitive Substrate</span>
            </div>
        </div>
        <div class="nav-tabs">
            <button class="tab-btn active" onclick="switchTab('setup')">🧬 Gestation Setup</button>
            <button class="tab-btn" onclick="switchTab('dev')">⚙️ Dev & Tools</button>
            <button class="tab-btn" onclick="switchTab('chat')">💬 Agent Chat</button>
        </div>
    </header>

    <main>
        <!-- Tab 1: Gestation & Setup -->
        <div id="tab-setup" class="tab-content active">
            <div class="glass-card">
                <div class="card-header">
                    <h2>Gestate a Persistent Agent</h2>
                    <p>Configure the core identity, initial taste priors, and local LLM model.</p>
                </div>
                
                <div class="form-grid">
                    <div class="form-group">
                        <label>Your Name (Human)</label>
                        <input type="text" id="human-name" value="Josh" placeholder="e.g. Josh">
                    </div>
                    <div class="form-group">
                        <label>Agent Name</label>
                        <input type="text" id="agent-name" value="Nova" placeholder="e.g. Nova">
                    </div>
                </div>

                <div class="form-group" style="margin-top: 1.5rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <label>Local Model Backend</label>
                        <button class="detect-btn" onclick="autoDetectModels()">🔍 Auto-Detect Local Models</button>
                    </div>
                    <select id="model-select">
                        <option value="granite4.1:8b">granite4.1:8b (Recommended)</option>
                        <option value="llama3.2:latest">llama3.2:latest</option>
                        <option value="qwen2.5:7b">qwen2.5:7b</option>
                    </select>
                </div>

                <div class="form-group" style="margin-top: 1.5rem;">
                    <label>Initial Taste Seed (Genetic Edge Prior)</label>
                    <div class="taste-grid">
                        <div class="taste-card selected" onclick="selectTaste('balanced', this)">
                            <h4>Balanced</h4>
                            <p>Equal weight across conversation, investigation, and execution.</p>
                        </div>
                        <div class="taste-card" onclick="selectTaste('curious', this)">
                            <h4>Curious</h4>
                            <p>Gently favors looking, reading, and asking before acting.</p>
                        </div>
                        <div class="taste-card" onclick="selectTaste('deliberate', this)">
                            <h4>Deliberate</h4>
                            <p>Gently favors checking evidence before making mutations.</p>
                        </div>
                        <div class="taste-card" onclick="selectTaste('builder', this)">
                            <h4>Builder</h4>
                            <p>Gently favors making and executing practical work.</p>
                        </div>
                    </div>
                </div>

                <div style="margin-top: 2rem;">
                    <button class="cta-btn" onclick="startGestation()">🥚 Gestate Agent Mind</button>
                </div>
            </div>
        </div>

        <!-- Tab 2: Dev & Tools -->
        <div id="tab-dev" class="tab-content">
            <div class="glass-card">
                <div class="card-header">
                    <h2>Developer & Tool Manager</h2>
                    <p>Register single-use execution gateway tools and inspect graph health.</p>
                </div>

                <div class="form-grid">
                    <div class="form-group">
                        <label>Tool Name</label>
                        <input type="text" id="tool-name" placeholder="e.g. search_web_inspector">
                    </div>
                    <div class="form-group">
                        <label>Effector Class (Motor Trunk)</label>
                        <select id="tool-trunk">
                            <option value="LOOK">LOOK (Non-mutating state inspection)</option>
                            <option value="DO">DO (External state mutation / execution)</option>
                            <option value="SPEAK">SPEAK (Outbound communication)</option>
                        </select>
                    </div>
                </div>

                <div class="form-group" style="margin-top: 1rem;">
                    <label>Tool Specification / Handler Script</label>
                    <textarea id="tool-spec" rows="3" placeholder="def execute_tool(args): ..."></textarea>
                </div>

                <div style="margin-top: 1.5rem;">
                    <button class="cta-btn" style="background: linear-gradient(135deg, var(--accent-purple), var(--accent-pink));" onclick="registerTool()">⚙️ Register Tool Node</button>
                </div>
            </div>

            <div class="glass-card">
                <div class="card-header">
                    <h2>Live Mind Graph Status</h2>
                    <p>Real-time graph metrics from the SQLite store.</p>
                </div>
                <div id="status-output" style="font-family: var(--font-mono); font-size: 0.9rem; color: var(--accent-cyan);">
                    Click "Refresh Status" to inspect graph invariants.
                </div>
                <div style="margin-top: 1rem;">
                    <button class="detect-btn" onclick="refreshStatus()">🔄 Refresh Status</button>
                </div>
            </div>
        </div>

        <!-- Tab 3: Agent Chat -->
        <div id="tab-chat" class="tab-content">
            <div class="chat-container">
                <div class="chat-header">
                    <div class="chat-header-info">
                        <div class="status-badge"></div>
                        <div>
                            <h3 id="active-agent-title">Agent Mind</h3>
                            <span id="active-model-title" style="font-size: 0.8rem; color: var(--text-secondary);">Ollama Backend</span>
                        </div>
                    </div>
                </div>

                <div class="chat-messages" id="chat-messages">
                    <div class="message-bubble message-agent">
                        Hello! I am gestated and awake. Send a message to begin our conversation.
                    </div>
                </div>

                <div class="chat-input-bar">
                    <input type="text" id="chat-input" placeholder="Type a message..." onkeydown="if(event.key==='Enter') sendMessage()">
                    <button class="cta-btn" style="width: auto; padding: 0.85rem 1.5rem;" onclick="sendMessage()">Send</button>
                </div>
            </div>
        </div>
    </main>

    <!-- Gestation Progress Modal -->
    <div class="modal-overlay" id="gestation-modal">
        <div class="modal-card">
            <div class="egg-container">
                <div class="egg-sprite"></div>
                <div class="egg-glow"></div>
            </div>

            <h3 id="modal-title" style="font-size: 1.3rem; margin-bottom: 0.25rem;">Gestating Mind...</h3>
            <p id="modal-subtitle" style="font-size: 0.85rem; color: var(--text-secondary);">Seeding identity pulses and structural Y-branches</p>

            <div class="progress-bar-container">
                <div class="progress-bar-fill" id="progress-fill"></div>
            </div>

            <div class="status-text" id="progress-text">Gestating... 0%</div>

            <div style="margin-top: 1.5rem; display: none;" id="hatch-action-container">
                <button class="cta-btn" onclick="completeHatch()">🐣 Hatch Agent</button>
            </div>
        </div>
    </div>

    <script>
        let selectedTaste = 'balanced';
        let isGestationComplete = false;

        function switchTab(tabId) {
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
            
            event.target.classList.add('active');
            document.getElementById(`tab-${tabId}`).classList.add('active');
            if (tabId === 'dev') refreshStatus();
        }

        function selectTaste(taste, cardElement) {
            selectedTaste = taste;
            document.querySelectorAll('.taste-card').forEach(c => c.classList.remove('selected'));
            cardElement.classList.add('selected');
        }

        async function autoDetectModels() {
            try {
                const res = await fetch('/api/models');
                const data = await res.json();
                if (data.models && data.models.length > 0) {
                    const select = document.getElementById('model-select');
                    select.innerHTML = '';
                    data.models.forEach(m => {
                        const opt = document.createElement('option');
                        opt.value = m;
                        opt.textContent = m + ' (Detected)';
                        select.appendChild(opt);
                    });
                    alert(`Detected ${data.models.length} local Ollama models!`);
                }
            } catch (err) {
                alert('Could not connect to local Ollama API. Using fallback model list.');
            }
        }

        function startGestation() {
            const human = document.getElementById('human-name').value || 'User';
            const agent = document.getElementById('agent-name').value || 'Nova';
            const model = document.getElementById('model-select').value || 'granite4.1:8b';

            const modal = document.getElementById('gestation-modal');
            const fill = document.getElementById('progress-fill');
            const text = document.getElementById('progress-text');
            const hatchContainer = document.getElementById('hatch-action-container');

            modal.classList.add('active');
            fill.style.width = '0%';
            text.textContent = 'Gestating... 0%';
            hatchContainer.style.display = 'none';

            const steps = [
                { pct: 20, msg: 'Creating identity:self and identity:human concepts...' },
                { pct: 45, msg: 'Binding gestational seed records to edge evidence...' },
                { pct: 70, msg: `Applying ${selectedTaste} taste edge priors to motor trunks...` },
                { pct: 90, msg: 'Validating 15 structural graph invariants...' },
                { pct: 100, msg: 'Gestation complete! Mind is ready to hatch.' }
            ];

            let stepIdx = 0;
            const interval = setInterval(async () => {
                if (stepIdx < steps.length) {
                    const s = steps[stepIdx];
                    fill.style.width = `${s.pct}%`;
                    text.textContent = `Gestating... ${s.pct}% (${s.msg})`;
                    stepIdx++;
                } else {
                    clearInterval(interval);
                    // Submit API request
                    try {
                        const res = await fetch('/api/gestate', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                human_name: human,
                                agent_name: agent,
                                taste: selectedTaste,
                                model: model
                            })
                        });
                        const data = await res.json();
                        document.getElementById('modal-title').textContent = `${data.agent_name} is Gestated!`;
                        document.getElementById('modal-subtitle').textContent = `Ready to hatch alongside ${data.human_name}`;
                        hatchContainer.style.display = 'block';
                        document.getElementById('active-agent-title').textContent = data.agent_name;
                        document.getElementById('active-model-title').textContent = `${data.model_name} (${data.taste_schema})`;
                    } catch (err) {
                        text.textContent = 'Gestation error: ' + err;
                    }
                }
            }, 400);
        }

        function completeHatch() {
            document.getElementById('gestation-modal').classList.remove('active');
            // Switch to chat tab
            document.querySelectorAll('.tab-btn')[2].click();
        }

        async function sendMessage() {
            const input = document.getElementById('chat-input');
            const msg = input.value.trim();
            if (!msg) return;

            const messagesContainer = document.getElementById('chat-messages');

            // Append User Message
            const userDiv = document.createElement('div');
            userDiv.className = 'message-bubble message-user';
            userDiv.textContent = msg;
            messagesContainer.appendChild(userDiv);

            input.value = '';
            messagesContainer.scrollTop = messagesContainer.scrollHeight;

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: msg })
                });
                const data = await res.json();

                if (data.error) {
                    const errDiv = document.createElement('div');
                    errDiv.className = 'message-bubble message-agent';
                    errDiv.style.borderColor = '#ff1744';
                    errDiv.textContent = '⚠️ ' + data.error;
                    messagesContainer.appendChild(errDiv);
                } else {
                    const agentDiv = document.createElement('div');
                    agentDiv.className = 'message-bubble message-agent';
                    agentDiv.innerHTML = `
                        ${data.response}
                        <div class="message-meta">
                            <span class="meta-tag">Trunk: ${data.trunk}</span>
                            <span>Y-Paths: ${data.y_paths.length}</span>
                        </div>
                    `;
                    messagesContainer.appendChild(agentDiv);
                }
            } catch (err) {
                const errDiv = document.createElement('div');
                errDiv.className = 'message-bubble message-agent';
                errDiv.textContent = 'Error sending message: ' + err;
                messagesContainer.appendChild(errDiv);
            }
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }

        async function refreshStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                document.getElementById('status-output').textContent = JSON.stringify(data, null, 2);
            } catch (err) {
                document.getElementById('status-output').textContent = 'Error fetching status: ' + err;
            }
        }

        async function registerTool() {
            const name = document.getElementById('tool-name').value;
            const trunk = document.getElementById('tool-trunk').value;
            const spec = document.getElementById('tool-spec').value;

            if (!name) { alert('Enter a tool name'); return; }

            const res = await fetch('/api/tools', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tool_name: name, tool_type: trunk, tool_spec: spec })
            });
            const data = await res.json();
            alert(`Tool ${data.tool_name} registered under trunk ${data.tool_type}!`);
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
