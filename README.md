# zcode-start-plan — Start Plan в терминале

Неофициальная инструкция и патчи, которые включают **Start Plan** (промо‑пул ZCode)
в открытом ZCode CLI, чтобы его токены тратились из терминала, а не только в приложении.

Проверено на Linux (Ubuntu, Node 24.22.1, ZCode 3.16.3, коммит `3c5b2276`).
Изначальный способ описан для macOS — здесь он воспроизведён и дополнен двумя правками,
без которых Start Plan молча не включается.

## Что раздают перед выходными

Промо **«ZCode 1024 Dev Day»** в кабинете Z.AI (план `zcode-v3-start-plan-1024`):

| Позиция | Объём | Срок |
|---|---|---|
| GLM-5.3-Flash | 300 000 000 токенов | до 26.10 04:00 MSK |
| GLM-5.3 | 200 000 000 токенов | до 26.10 04:00 MSK |

Итого 500 млн токенов на два дня, `period: one_time`, статус `active`.
Дневная бесплатная квота Start Plan расходуется **первой**, приз — когда она кончится;
поэтому карточки в приложении долго показывают 100 %, и кажется, что приз не тратится.

Подробности, включая снятые с биллинга остатки: [docs/promo.md](docs/promo.md).

## Почему «просто поставить ключ» не работает

Start Plan живёт только на шлюзах `zcode.z.ai/api/v1/zcode-plan/*`, и они принимают
не API‑ключ, а сессию ZCode (заголовки `Authorization` + `X-Bigmodel-Authorization` +
`Bigmodel-Target-Type: PERSONAL`). Схема `ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic`
+ ключ из консоли работает, но списывает с **личного** coding plan — при этом расход
приза остаётся нулевым. Единственный способ тратить приз — клиент ZCode: приложение
или собранный с патчем CLI.

## Быстрый старт

```bash
# 1. Сборка (Node 24!)
git init zcode && cd zcode
git remote add origin https://github.com/zai-org/ZCode
git fetch --depth 1 origin 3c5b227649371507ddc4eb46ac5133afe6db1cab
git checkout -q FETCH_HEAD
git apply ../patch/0001-start-plan.patch
git apply ../patch/0002-device-mid-and-retry.patch
npx --yes pnpm@10.33.2 install --frozen-lockfile --filter "@zcode/cli..."
npx --yes pnpm@10.33.2 --filter "@zcode/cli..." build

# 2. Логин — окно 5 минут, подтвердить в браузере сразу
cp ~/.zcode/v2/credentials.json ~/.zcode/v2/credentials.json.bak-$(date +%s)
/usr/bin/node apps/zcode-cli/packages/cli/dist/zcode.cjs login zai

# 3. Start Plan по умолчанию
node set-start-plan-default.mjs GLM-5.3 high

# 4. Проверка
ZCODE_DEBUG_START_PLAN=1 /usr/bin/node apps/zcode-cli/packages/cli/dist/zcode.cjs -p "тест"
python3 scripts/check-balance.py
```

Полная пошаговая инструкция со всеми ловушками: [docs/howto.md](docs/howto.md).

## Что лежит в репозитории

```
patch/0001-start-plan.patch          патч Start Plan для открытого CLI (Apache-2.0, апстрим-архив)
patch/0002-device-mid-and-retry.patch  две правки: device_mid в billing/balance + ретраи
docs/howto.md                        пошагово: сборка, логин, проверки, грабли
docs/promo.md                        что раздают, сроки, наблюдённые остатки
scripts/build.sh                     сборка одной командой
scripts/zcode-start-plan             обёртка запуска (всегда node 24)
scripts/check-balance.py             читает used_units из billing/balance
```

## Две правки, без которых не работает

1. **`device_mid` в запросе баланса.** Без него `billing/balance` отвечает
   `400 {"code":3001,"msg":"parameter error"}`, список моделей Start Plan не разрешается,
   и CLI молча уходит на провайдера `zai-api` (обычный API‑ключ, личный план).
2. **Ретраи.** Эндпоинт периодически таймаутит; одного сбоя хватает, чтобы Start Plan
   не включился.

Обе правки — в `patch/0002-device-mid-and-retry.patch`.

## Как убедиться, что тратится приз

```bash
# провайдер последнего прогона: должно быть account:zai-start-plan, а не zai-api
f=$(ls -t ~/.zcode/cli/rollout/*.jsonl | head -1)
grep -oE '"(providerId|modelId|inputTokens|outputTokens)":[^,}]*' "$f"

# расход: used_units должен расти
python3 scripts/check-balance.py
```

Экран подписки в приложении — не доказательство: он показывает процент дневной квоты.

## Предупреждения

- Неофициально. Патч меняет клиент ZCode; условия обслуживания Z.AI могут это запрещать.
  Риск блокировки аккаунта — на том, кто применяет.
- `zcode login zai` **перезаписывает** общий `~/.zcode/v2/credentials.json` и стирает
  токены приложения. Копию делать до логина, приложение после — логинить заново.
- Промо ограничено по времени и по аккаунту. Когда план истечёт, `balances` вернётся
  пустым, `startPlanModelIds` не разрешится, и CLI уйдёт на личный план.
- В репозитории нет ключей и токенов: доступы читаются из локального стора ZCode.

## Лицензия

Apache License 2.0 — см. [LICENSE](LICENSE) и [NOTICE.md](NOTICE.md).
Патч `0001` распространяется на условиях апстрим-архива, `0002` — на тех же условиях.
