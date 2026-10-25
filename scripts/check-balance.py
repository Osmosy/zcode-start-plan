#!/usr/bin/env python3
"""Печатает расход Start Plan: used_units / remaining_units по каждой позиции.

Читает zcodejwttoken из локального стора ZCode (расшифровывает AES-256-GCM),
добавляет обязательные query-параметры app_version и device_mid — без них
billing/balance отвечает 400 parameter error. Ретраит: эндпоинт периодически
таймаутит.
"""
import base64
import hashlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(os.environ.get("ZCODE_DATA_BASE_DIR", Path.home() / ".zcode"))
CREDS = BASE / "v2" / "credentials.json"
TELEMETRY = BASE / "v2" / "telemetry-state.json"
ENDPOINT = "https://zcode.z.ai/api/v1/zcode-plan/billing/balance"
APP_VERSION = os.environ.get("ZCODE_STANDALONE_APP_VERSION", "3.16.3")


def cipher_key() -> bytes:
    secret = os.environ.get("ZCODE_CREDENTIAL_SECRET") or (
        f"zcode-credential-fallback:{sys.platform if sys.platform == 'darwin' else 'linux'}:"
        f"{Path.home()}:{os.environ.get('USER') or os.environ.get('LOGNAME') or 'unknown'}"
    )
    return hashlib.sha256(secret.encode()).digest()


def decrypt(value: str) -> str:
    if not value.startswith("enc:v1:"):
        return value
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    iv_b64, tag_b64, ct_b64 = value[6:].split(".")
    pad = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
    return AESGCM(cipher_key()).decrypt(pad(iv_b64), pad(ct_b64) + pad(tag_b64), None).decode()


def main() -> int:
    if not CREDS.exists():
        print(f"нет {CREDS} — сначала zcode login zai", file=sys.stderr)
        return 1
    jwt = decrypt(json.loads(CREDS.read_text())["zcodejwttoken"]).strip()
    device_mid = json.loads(TELEMETRY.read_text()).get("deviceMid", "") if TELEMETRY.exists() else ""
    url = f"{ENDPOINT}?app_version={APP_VERSION}"
    if device_mid:
        url += f"&device_mid={device_mid}"

    last_error = None
    for attempt in range(1, 4):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bearer {jwt}",
                    "Bigmodel-Target-Type": "PERSONAL",
                },
            )
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = json.load(response)
            break
        except Exception as error:  # noqa: BLE001
            last_error = error
            print(f"попытка {attempt}: {type(error).__name__}", file=sys.stderr)
            time.sleep(3)
    else:
        print(f"billing/balance недоступен: {last_error}", file=sys.stderr)
        return 2

    if payload.get("code") != 0:
        print(f"ответ {payload.get('code')}: {payload.get('msg')}", file=sys.stderr)
        return 2

    balances = (payload.get("data") or {}).get("balances") or []
    if not balances:
        print("приз не активен: список балансов пуст")
        return 0
    for item in balances:
        print(
            f"{item.get('show_name', '?'):15} used={item.get('used_units', 0):>10} "
            f"remaining={item.get('remaining_units', 0):>12} "
            f"total={item.get('total_units', 0):>12}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
