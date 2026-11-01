#!/usr/bin/env python3
# Copyright 2026 Osmosy
# Licensed under the Apache License, Version 2.0 (see LICENSE in the repository root).
"""Минимальный ACP-агент поверх ZCode CLI (Start Plan).

Задача: дать оболочкам, которые умеют только ACP (например T3 Code, Zed),
доступ к ZCode через канал Start Plan, который работает лишь через клиент
ZCode. Агент говорит по Agent Client Protocol (JSON-RPC построчно через stdio)
и на каждый prompt запускает `zcode --prompt ... --json`, возвращая текст
ответа как agent_message_chunk.

Ограничения честно:
  * это не полноценный ACP — поддерживаются initialize, session/new,
    session/prompt, session/cancel; нет images, tool-вызовов в протоколе
    (инструменты исполняет сам ZCode у себя) и нет permission-запросов;
  * каждая реплика — отдельный процесс; непрерывность держится на --resume;
  * используется только стандартная библиотека.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path

REPO_LAUNCHER = Path(__file__).resolve().parent.parent / "scripts" / "zcode-start-plan"
ZCODE = (
    os.environ.get("ZCODE_ACP_BIN")
    or (str(REPO_LAUNCHER) if REPO_LAUNCHER.exists() else None)
    or shutil.which("zcode-start-plan")
    or shutil.which("zcode")
)
PROTOCOL_VERSION = 1
AGENT_NAME = "ZCode Start Plan"
AGENT_VERSION = "0.1.0"

_sessions: dict[str, dict] = {}
_write_lock = threading.Lock()
_procs: dict[str, subprocess.Popen] = {}


def send(payload: dict) -> None:
    line = json.dumps(payload, ensure_ascii=False)
    with _write_lock:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()


def reply(req_id, result=None, error=None) -> None:
    msg: dict = {"jsonrpc": "2.0", "id": req_id}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    send(msg)


def notify(method: str, params: dict) -> None:
    send({"jsonrpc": "2.0", "method": method, "params": params})


def chunk(session_id: str, text: str) -> None:
    notify(
        "session/update",
        {
            "sessionId": session_id,
            "update": {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": text},
            },
        },
    )


def prompt_text(blocks) -> str:
    parts: list[str] = []
    for block in blocks or []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text") or "")
    return "\n".join(p for p in parts if p).strip()


def run_zcode(session: dict, text: str) -> str:
    """Один вызов ZCode; возвращает текст ответа. Сохраняет sessionId для --resume."""
    cmd = [ZCODE, "-p", text, "--cwd", session["cwd"], "--json"]
    if session.get("mode"):
        cmd += ["--mode", session["mode"]]
    if session.get("zcode_session"):
        cmd += ["--resume", session["zcode_session"]]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "NO_COLOR": "1"},
    )
    _procs[session["id"]] = proc
    try:
        out, err = proc.communicate(timeout=int(os.environ.get("ZCODE_ACP_TIMEOUT", "900")))
    finally:
        _procs.pop(session["id"], None)

    raw = (out or "").strip()
    if not raw:
        return f"ZCode не вернул ответ. Код {proc.returncode}. {err.strip()[:800]}"

    # --json печатает объект; на случай лишних строк берём последний валидный JSON
    data = None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        for line in reversed(raw.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    data = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue

    if not isinstance(data, dict):
        return raw

    sid = data.get("sessionId")
    if isinstance(sid, str) and sid.startswith("sess_"):
        session["zcode_session"] = sid

    response = data.get("response")
    if isinstance(response, str) and response.strip():
        return response.strip()

    return raw


def handle(req: dict) -> None:
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        reply(
            req_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "agentCapabilities": {
                    "loadSession": False,
                    "promptCapabilities": {
                        "image": False,
                        "audio": False,
                        "embeddedContext": False,
                    },
                },
                "authMethods": [],
                "agentInfo": {"name": AGENT_NAME, "version": AGENT_VERSION},
            },
        )
        return

    if method == "session/new":
        sid = f"sess_{uuid.uuid4().hex[:16]}"
        cwd = params.get("cwd") or os.getcwd()
        _sessions[sid] = {"id": sid, "cwd": cwd, "zcode_session": None, "mode": os.environ.get("ZCODE_ACP_MODE")}
        # Каталог моделей: без него клиенты вроде T3 Code не дают выбрать провайдера.
        # Реальную модель выбирает сам ZCode по своим настройкам, поэтому список условный.
        model_id = os.environ.get("ZCODE_ACP_MODEL", "zcode-default")
        reply(
            req_id,
            {
                "sessionId": sid,
                "models": {
                    "availableModels": [
                        {
                            "modelId": model_id,
                            "name": os.environ.get("ZCODE_ACP_MODEL_NAME", "ZCode (Start Plan)"),
                            "description": "Модель выбирается настройками ZCode; обёртка её не переопределяет.",
                        }
                    ],
                    "currentModelId": model_id,
                },
            },
        )
        return

    if method in ("session/set_model", "session/setModel"):
        # Принимаем выбор модели, но не передаём его в ZCode: там своя настройка.
        reply(req_id, {})
        return

    if method in ("session/load", "session/resume"):
        sid = params.get("sessionId") or params.get("session_id")
        if sid in _sessions:
            reply(req_id, {})
        else:
            reply(req_id, error={"code": -32602, "message": "unknown session"})
        return

    if method == "session/prompt":
        sid = params.get("sessionId")
        session = _sessions.get(sid)
        if not session:
            reply(req_id, error={"code": -32602, "message": f"unknown session {sid}"})
            return
        text = prompt_text(params.get("prompt"))
        if not text:
            reply(req_id, {"stopReason": "end_turn"})
            return
        try:
            answer = run_zcode(session, text)
        except subprocess.TimeoutExpired:
            answer = "ZCode не ответил за отведённое время."
        except Exception as exc:  # noqa: BLE001 — демон не должен падать из-за одной реплики
            answer = f"Ошибка запуска ZCode: {exc}"
        chunk(sid, answer)
        reply(req_id, {"stopReason": "end_turn"})
        return

    if method == "session/cancel":
        sid = params.get("sessionId")
        proc = _procs.get(sid)
        if proc and proc.poll() is None:
            proc.terminate()
        return  # нотификация, ответа не ждёт

    if req_id is not None:
        reply(req_id, error={"code": -32601, "message": f"method not found: {method}"})


def main() -> None:
    if not ZCODE:
        sys.stderr.write("zcode-acp: не найден zcode-start-plan или zcode в PATH\n")
        sys.exit(2)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(req, dict):
            handle(req)


if __name__ == "__main__":
    main()
