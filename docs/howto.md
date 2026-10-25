ZCode Start Plan в терминале — как это было сделано (25.10.2026)
=================================================================

Итог: приз «ZCode 1024 Dev Day» (300M GLM-5.3-Flash + 200M GLM-5.3) тратится
из терминала через собранный с патчем ZCode CLI. Проверка — биллинг: used_units
вырос с 0 до 101 288 / 152 240.

Start Plan живёт ТОЛЬКО на шлюзах zcode.z.ai/api/v1/zcode-plan/*, и они принимают
не API-ключ, а сессию ZCode. Поэтому Claude Code (ANTHROPIC_BASE_URL + ключ из
консоли) к призу не подключается — он всегда списывает с личного coding plan.


1. ГДЕ ЧТО ЛЕЖИТ
-----------------------------------------------------------------
Архив распакован:   ~/.hermes/cache/scratch/zcode-start-plan/
Исходники + сборка: ~/zcode            (пин 3c5b227649371507ddc4eb46ac5133afe6db1cab)
Бандл CLI:          ~/zcode/apps/zcode-cli/packages/cli/dist/zcode.cjs (29 МБ)
Обёртка запуска:    ~/.local/bin/zcode-start-plan
Мой дифф к патчу:   ~/.hermes/cache/scratch/zcode-start-plan-device-mid.patch
Навык (краткая версия): zcode-start-plan-cli


2. СБОРКА (Node 24 обязателен; 22 ломает TUI)
-----------------------------------------------------------------
cd ~ && rm -rf zcode && mkdir zcode && cd zcode
git init -q
git remote add origin https://github.com/zai-org/ZCode
git fetch --depth 1 origin 3c5b227649371507ddc4eb46ac5133afe6db1cab
git checkout -q FETCH_HEAD
git apply ~/.hermes/cache/scratch/zcode-start-plan/zcode-start-plan.patch

npx --yes pnpm@10.33.2 install --frozen-lockfile --filter "@zcode/cli..."
npx --yes pnpm@10.33.2 --filter "@zcode/cli..." build

# проверка: должна выйти версия 0.17.0
/usr/bin/node apps/zcode-cli/packages/cli/dist/zcode.cjs --version

Важно: в login-шелле (bash -lic) PATH даёт ~/.local/bin/node = v22.22.3,
а /usr/bin/node = v24.22.1. Запускать всегда /usr/bin/node.


3. ЛОГИН — ОКНО РОВНО 5 МИНУТ
-----------------------------------------------------------------
cd ~/zcode
cp ~/.zcode/v2/credentials.json ~/.zcode/v2/credentials.json.bak-$(date +%s)   # ОБЯЗАТЕЛЬНО, см. п.7
BROWSER=firefox /usr/bin/node apps/zcode-cli/packages/cli/dist/zcode.cjs login zai

В выводе появится Fallback URL на chat.z.ai/api/oauth/authorize... — открыть и
подтвердить НЕМЕДЛЕННО. Таймаут задан в bootstrap/src/auth-login.ts:
DEFAULT_LOGIN_TIMEOUT_MS = 5 * 60 * 1000. Если подтвердить после — сервер отдаёт
«Authorization Failed» (logid ...), потому что принимает код от истёкшего state.

Успех выглядит так:
  Login successful as Mikhail.
  Model: account:zai-individual-coding-plan/GLM-5.3
  Credentials: /home/lenovo/.zcode/v2/credentials.json
  Model selection: /home/lenovo/.zcode/v2/provider_config.json

Сервер иногда отдаёт 502 на init — просто повторить запуск (2-3 раза).


4. СДЕЛАТЬ START PLAN ПРОВАЙДЕРОМ ПО УМОЛЧАНИЮ
-----------------------------------------------------------------
cd ~/.hermes/cache/scratch/zcode-start-plan
/usr/bin/node set-start-plan-default.mjs            # GLM-5.3, reasoning high
# в ~/.zcode/v2/provider_config.json появится:
#   "defaultModelSelection": {"providerId":"account:zai-start-plan","modelId":"GLM-5.3",
#                             "options":{"reasoningLevel":"high"}}
# и бэкап provider_config.json.bak-<дата>


5. ДВЕ ПРАВКИ В ПАТЧ (без них Start Plan не включается)
-----------------------------------------------------------------
Файл: ~/zcode/apps/zcode-cli/packages/bootstrap/src/app/standalone-account-provider-runtime.ts

5.1 device_mid в запросе баланса.
    billing/balance без него отвечает 400 {"code":3001,"msg":"parameter error"},
    startPlanModelIds не разрешается, и CLI молча уходит на провайдера zai-api
    (обычный API-ключ, личный план). Приложение тем же URL с device_mid получает 200.
    deviceMid берётся из ~/.zcode/v2/telemetry-state.json.

    После url.searchParams.set("app_version", ...) вставить:

      const deviceMid = resolveStartPlanDeviceMid(env);
      if (deviceMid) url.searchParams.set("device_mid", deviceMid);

    И рядом добавить функцию (импорты readFileSync, homedir, join):

      function resolveStartPlanDeviceMid(
        env: Readonly<Record<string, string | undefined>>,
      ): string | undefined {
        const fromEnv = env.ZCODE_DEVICE_MID?.trim();
        if (fromEnv) return fromEnv;
        try {
          const baseDir = env.ZCODE_DATA_BASE_DIR?.trim() || join(homedir(), ".zcode");
          const parsed = JSON.parse(
            readFileSync(join(baseDir, "v2", "telemetry-state.json"), "utf8"),
          ) as { deviceMid?: string };
          return parsed.deviceMid?.trim() || undefined;
        } catch {
          return undefined;
        }
      }

5.2 Ретраи. Эндпоинт баланса периодически таймаутит (15 с), и одного сбоя хватает,
    чтобы Start Plan не включился. Заменить одиночный fetch на цикл:

      let response: Response | undefined;
      for (let attempt = 1; attempt <= 3; attempt += 1) {
        try {
          response = await fetch(url, {
            headers: { Authorization: `Bearer ${jwt}` },
            signal: AbortSignal.timeout(START_PLAN_BALANCE_TIMEOUT_MS),
          });
          if (response.ok) break;
        } catch (error) {
          if (env.ZCODE_DEBUG_START_PLAN)
            console.warn("[start-plan-debug] balance attempt", attempt, String(error));
          response = undefined;
        }
        if (attempt < 3) await new Promise((resolve) => setTimeout(resolve, 1_500));
      }
      if (!response) return undefined;

Затем пересборка (25 секунд, зависимости уже стоят):
      cd ~/zcode && npx --yes pnpm@10.33.2 --filter "@zcode/cli..." build


6. ПРОВЕРКА, ЧТО ТРАТИТСЯ ИМЕННО ПРИЗ
-----------------------------------------------------------------
6.1 Отладка прогона:
      cd ~/zcode && ZCODE_DEBUG_START_PLAN=1 \
        timeout 150 /usr/bin/node apps/zcode-cli/packages/cli/dist/zcode.cjs -p "Скажи ровно: готово"

    Ожидаемо:
      [start-plan-debug] balance 200 0  [ ['GLM-5.3-Flash',['model:glm-5.3-flash']],
                                          ['GLM-5.3',['model:glm-5.3']] ]
      jwtPresent: true
      startPlanModelIds: [ 'GLM-5.3-Flash', 'GLM-5.3' ]
      готово

6.2 Провайдер последнего прогона (должен быть account:zai-start-plan, НЕ zai-api):
      f=$(ls -t ~/.zcode/cli/rollout/*.jsonl | head -1)
      grep -oE '"(providerId|modelId|inputTokens|outputTokens)":[^,}]*' "$f"

6.3 Расход в биллинге (единственное настоящее доказательство):

      python3 - <<'PY'
      import json, hashlib, base64, urllib.request
      from cryptography.hazmat.primitives.ciphers.aead import AESGCM
      key = hashlib.sha256("zcode-credential-fallback:linux:/home/lenovo:lenovo".encode()).digest()
      c = json.load(open("/home/lenovo/.zcode/v2/credentials.json"))
      def dec(v):
          iv, tag, ct = (base64.urlsafe_b64decode(x + "=" * (-len(x) % 4)) for x in v[6:].split("."))
          return AESGCM(key).decrypt(iv, ct + tag, None).decode()
      jwt = dec(c["zcodejwttoken"])
      mid = json.load(open("/home/lenovo/.zcode/v2/telemetry-state.json"))["deviceMid"]
      url = ("https://zcode.z.ai/api/v1/zcode-plan/billing/balance"
             "?app_version=3.16.3&device_mid=" + mid)
      d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={
          "Authorization": "Bearer " + jwt, "Bigmodel-Target-Type": "PERSONAL"})))
      for b in d["data"]["balances"]:
          print(b["show_name"], "used=", b["used_units"], "остаток=", b["remaining_units"])
      PY


7. ГРАБЛИ (все проверены на себе)
-----------------------------------------------------------------
* zcode login zai ПЕРЕЗАПИСЫВАЕТ общий ~/.zcode/v2/credentials.json и стирает
  токены приложения (oauth:zai:access_token, zcodejwttoken, api-key). После этого
  приложение стартует пустым и в логе 401. Лечение: войти заново в приложении —
  оно допишет свои ключи (проверено, файл вырос с 3 до 7 записей). Копию делать ДО login.
* Старый zcodejwttoken из Local Storage приложения (~/.config/ZCode/session/
  Partitions/zcode-coding-plan/Local Storage/leveldb) НЕ подходит: форма та же,
  сервер отвечает 400. Нужен свежий от только что залогиненного приложения.
* app_version = 0.0.0-dev отвергается: задавать ZCODE_STANDALONE_APP_VERSION
  равным версии установленного приложения (3.16.3).
* «model concurrency limit exceeded» (providerCode 3009) на Start Plan — штатное
  на первом запросе серии; повтор через 5-10 секунд проходит.
* Креды в credentials.json лежат как enc:v1:<iv>.<tag>.<ciphertext>, AES-256-GCM,
  ключ = sha256(env ZCODE_CREDENTIAL_SECRET или
  "zcode-credential-fallback:linux:/home/lenovo:lenovo"). Этого достаточно, чтобы
  прочитать или дописать запись в стор без запуска приложения.
* Клик по «Authorize» в браузере: у нас приложение на Wayland, wmctrl/xdotool и
  computer_use его окно не видят — авторизацию завершает пользователь вручную.


8. ЧАСТЬ 1 — ПРИЛОЖЕНИЕ (без патчей)
-----------------------------------------------------------------
Приложение и CLI читают один и тот же ~/.zcode/v2/provider_config.json, поэтому
defaultModelSelection = account:zai-start-plan уже прописан (п.4).
В самом приложении тариф выбирается в поле ввода: верхняя строка селектора модели —
  «Start Plan · Free» (в настройках Settings → Model settings видны карточки
  приза и дневной бесплатной квоты).
Сначала расходуется дневная квота Start Plan, приз — когда она кончится; поэтому
карточки долго показывают 100% и кажется, что приз не тратится.
Проверять надо не экран подписки, а used_units в billing/balance.


9. ЗАПУСК НА КАЖДЫЙ ДЕНЬ
-----------------------------------------------------------------
zcode-start-plan -p "запрос"    # одиночный прогон
zcode-start-plan               # TUI

Содержимое обёртки ~/.local/bin/zcode-start-plan:
  #!/usr/bin/env bash
  exec /usr/bin/node "$HOME/zcode/apps/zcode-cli/packages/cli/dist/zcode.cjs" "$@"


10. СОСТОЯНИЕ НА МОМЕНТ ЗАПИСИ (25.10.2026, 18:40 MSK)
-----------------------------------------------------------------
GLM-5.3-Flash  used 101 288 из 300 000 000   (остаток 299 898 712)
GLM-5.3        used 152 240 из 200 000 000   (остаток 199 847 760)
План: zcode-v3-start-plan-1024, active, ends_at 26.10 04:00 MSK.
