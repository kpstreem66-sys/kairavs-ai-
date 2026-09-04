from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
LOCAL_DIR = BASE_DIR / ".kai_local"
LOCAL_DIR.mkdir(exist_ok=True, parents=True)
PROVIDER_FILE = LOCAL_DIR / "provider_configs.json"
LEARNING_FILE = LOCAL_DIR / "kai_learning_memory.json"

SUPPORTED_PROTOCOLS = ["8-bit", "16-bit", "32-bit"]


def ensure_storage() -> None:
    LOCAL_DIR.mkdir(exist_ok=True, parents=True)
    PROVIDER_FILE.touch(exist_ok=True)
    LEARNING_FILE.touch(exist_ok=True)


def load_json(path: Path, default):
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(exist_ok=True, parents=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def load_providers():
    ensure_storage()
    raw = load_json(PROVIDER_FILE, {"providers": []})
    return raw.get("providers", [])


def save_providers(providers):
    ensure_storage()
    save_json(PROVIDER_FILE, {"providers": providers})


def load_learning_memory():
    ensure_storage()
    raw = load_json(LEARNING_FILE, [])
    if isinstance(raw, dict):
        return raw.get("learning", [])
    return raw if isinstance(raw, list) else []


def save_learning_memory(entries):
    ensure_storage()
    save_json(LEARNING_FILE, {"learning": entries})


def normalize_text(value: str) -> str:
    return " ".join(str(value).strip().split())


def provider_exists(name: str) -> bool:
    name = (name or "").strip().lower()
    return any((p.get("name", "").strip().lower() == name) for p in load_providers())


def get_provider_by_name(name: str):
    name = (name or "").strip().lower()
    for item in load_providers():
        if item.get("name", "").strip().lower() == name:
            return item
    return None


def _http_probe(provider: dict, message: str) -> str:
    payload = {
        "model": provider.get("model") or "gpt-4o-mini",
        "messages": [{"role": "user", "content": message}],
        "max_tokens": 64,
    }
    headers = {"Content-Type": "application/json"}
    api_key = (provider.get("api_key") or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    url = (provider.get("base_url") or "").rstrip("/")
    if not url:
        return ""

    if "/chat/completions" not in url and "/v1/chat/completions" not in url:
        url = f"{url}/chat/completions"

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        if response.status_code >= 400:
            return ""
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return ""
        content = choices[0].get("message", {}).get("content", "")
        if isinstance(content, list):
            content = "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
        return str(content).strip()
    except Exception:
        return ""


def learning_handshake_for_provider(provider: dict):
    for protocol in SUPPORTED_PROTOCOLS:
        challenge = (
            f"KAI-LEARNING-HANDSHAKE:{protocol}:Reply exactly 'KAI_PROTOCOL_OK:{protocol}' and nothing else."
        )
        response = _http_probe(provider, challenge)
        if f"KAI_PROTOCOL_OK:{protocol}" in response.upper():
            return protocol
    return None


def add_learning_fact(fact: str):
    fact = normalize_text(fact)
    if not fact or len(fact) < 4:
        return False
    entries = load_learning_memory()
    fact_lower = fact.lower()
    for item in entries:
        if normalize_text(str(item.get("fact", "")).lower()) == fact_lower:
            return False
    entries.append({
        "fact": fact,
        "source": "conversation",
        "created_at": date.today().isoformat(),
        "type": "user_taught_fact",
    })
    save_learning_memory(entries)
    return True


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/providers", methods=["GET", "POST", "DELETE"])
def manage_providers():
    providers = load_providers()
    if request.method == "GET":
        return jsonify({"providers": providers})

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        record = {
            "provider_id": data.get("provider_id") or os.urandom(8).hex(),
            "name": (data.get("name") or "").strip(),
            "provider_type": (data.get("provider_type") or "custom").strip().lower(),
            "base_url": (data.get("base_url") or "").strip(),
            "api_key": (data.get("api_key") or "").strip(),
            "model": (data.get("model") or "").strip(),
            "org_id": (data.get("org_id") or "").strip(),
            "project_id": (data.get("project_id") or "").strip(),
            "conversation_enabled": bool(data.get("conversation_enabled")),
            "fast_learning_enabled": bool(data.get("fast_learning_enabled")),
            "status": "active",
        }

        if not record["name"]:
            return jsonify({"ok": False, "message": "Provider name is required."}), 400

        existing = get_provider_by_name(record["name"])
        if existing:
            record["provider_id"] = existing["provider_id"]
            providers = [p for p in providers if p.get("provider_id") != existing["provider_id"]]
        providers.append(record)
        save_providers(providers)
        return jsonify({"ok": True, "provider": record})

    if request.method == "DELETE":
        name = (request.args.get("name") or "").strip()
        if not name:
            return jsonify({"ok": False, "message": "Provider name required."}), 400
        providers = [p for p in providers if p.get("name", "").strip().lower() != name.lower()]
        save_providers(providers)
        return jsonify({"ok": True, "providers": providers})

    return jsonify({"ok": False, "message": "Unsupported method."}), 405


@app.route("/api/providers/test", methods=["POST"])
def test_provider_route():
    data = request.get_json(silent=True) or {}
    provider = {
        "name": (data.get("name") or "").strip(),
        "provider_type": (data.get("provider_type") or "custom").strip().lower(),
        "base_url": (data.get("base_url") or "").strip(),
        "api_key": (data.get("api_key") or "").strip(),
        "model": (data.get("model") or "").strip(),
    }
    if not provider["name"] or not provider["base_url"]:
        return jsonify({"ok": False, "message": "Provider name and endpoint are required."}), 400

    response = _http_probe(provider, "ping")
    if response:
        return jsonify({"ok": True, "message": "Connection successful."})
    return jsonify({"ok": False, "message": "Connection failed or endpoint did not reply."})


@app.route("/api/fast-learning", methods=["POST"])
def fast_learning_route():
    data = request.get_json(silent=True) or {}
    provider_name = (data.get("provider_name") or "").strip()
    provider = get_provider_by_name(provider_name)
    if not provider:
        return jsonify({"ok": False, "message": "No saved provider selected."}), 400
    if not provider.get("fast_learning_enabled"):
        return jsonify({"ok": False, "message": "This provider is not enabled for Fast Learning."}), 400

    protocol = learning_handshake_for_provider(provider)
    if not protocol:
        return jsonify({"ok": False, "message": "KAI learning handshake failed. This provider cannot be used as a Fast Learning teacher."})

    lesson = (
        "KAI verified compatibility with the selected teacher using the required binary learning handshake "
        f"({protocol}). This lesson is now saved in KAI learning memory."
    )
    add_learning_fact(f"Fast Learning teacher: {provider['name']} | protocol: {protocol} | lesson: {lesson}")

    return jsonify({
        "ok": True,
        "provider": provider["name"],
        "protocol": protocol,
        "message": "Fast Learning started after a successful binary handshake.",
    })


@app.route("/api/conversation-learning", methods=["POST"])
def conversation_learning_route():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"ok": False, "message": "No message to learn."}), 400

    if "learn this" in message.lower() or "remember this" in message.lower() or "i prefer" in message.lower() or "my name is" in message.lower():
        stored = add_learning_fact(message)
        if stored:
            return jsonify({"ok": True, "message": "Useful information saved to KAI learning memory."})
        return jsonify({"ok": True, "message": "This learning fact was already known or was too short to store."})

    return jsonify({"ok": False, "message": "No useful learning fact detected."})


@app.route("/api/learning-memory", methods=["GET"])
def learning_memory_route():
    return jsonify({"learning": load_learning_memory()})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
