# Что раздают перед выходными

Снято с кабинета Z.AI и подтверждено запросом `billing/balance` (30.10.2026).

## Это повторяется

Подобный пул выдают почти каждые выходные: новый `plan_id` вида
`zcode-v3-start-plan-<ММДД>`, объёмы и срок меняются, живёт до 04:00 утра после
выходных. При новом промо пересобирать CLI не нужно — достаточно проверить
`billing/balance` и убедиться, что `startPlanModelIds` разрешается. Когда пул
пуст, CLI молча уходит на личный coding plan, поэтому `python3 scripts/check-balance.py`
перед работой — обязательный шаг, а не проверка «на всякий случай».

## Текущий пул: «ZCODE WEEKEND BUILD» (30.10 – 02.11.2026)

```
plan_id:        zcode-v3-start-plan-1030-wk
name:           ZCODE WEEKEND BUILD
status:         active
priority:       101
starts_at:      30.10.2026 15:19 MSK (effective 18:00 MSK)
ends_at:        02.11.2026 04:00 MSK
```

### Позиции (entitlements)

| entitlement_id | Модель | Объём | period |
|---|---|---|---|
| `ent-zcode-v3-start-plan-1030-wk-1` | GLM-5.3-Flash | 500 000 000 | one_time |

Единица измерения — токены (`meter: model_usage`, `unit_type: token`),
capability `model:glm-5.3-flash`.

**Отличие от прошлого пула:** позиция одна. GLM-5.3 (не-Flash) в этот пул не
выдавали, `startPlanModelIds` содержит только `GLM-5.3-Flash`. Все 500 млн — Flash.

### Наблюдённые остатки

| Момент | GLM-5.3-Flash used | remaining |
|---|---|---|
| 30.10, 18:06 (первый боевой прогон CLI) | 48 422 | 499 951 578 |
| 30.10, 18:13 (контроль) | 48 422 | 499 951 578 |

Селектор после открытия: `account:zai-start-plan` / `GLM-5.3-Flash`,
`reasoningLevel: high`. Ключ лежит в обёртке `config` файла
`~/.zcode/v2/provider_config.json`, на верхнем уровне его нет.

## Предыдущий пул: «ZCode 1024 Dev Day» (23 – 26.10.2026)

```
plan_id:        zcode-v3-start-plan-1024
name:           ZCode 1024 Dev Day
status:         active
starts_at:      23.10.2026 ~14:00 MSK
ends_at:        26.10.2026 04:00 MSK
priority:       101
```

| entitlement_id | Модель | Объём | period |
|---|---|---|---|
| `ent-zcode-v3-start-plan-1024-1` | GLM-5.3-Flash | 300 000 000 | one_time |
| `ent-zcode-v3-start-plan-1024-2` | GLM-5.3 | 200 000 000 | one_time |

Единица измерения — токены (`meter: model_usage`, `unit_type: token`).
Capabilities: `model:glm-5.3-flash` и `model:glm-5.3` соответственно.

| Момент | GLM-5.3-Flash used | GLM-5.3 used |
|---|---|---|
| 25.10, 17:47 (приз не тронут) | 0 | 0 |
| 25.10, 18:35 (после прогонов через CLI) | 101 288 | 152 240 |
| 25.10, 18:40 (контроль) | 101 288 | 152 240 |

Остаток на 18:40 MSK: 299 898 712 Flash + 199 847 760 GLM-5.3.

## Как расходуется

- Сначала списывается **дневная бесплатная квота Start Plan**, приз — только когда
  она исчерпана. Поэтому первое время обе карточки показывают 100 %, и создаётся
  впечатление, что приз не тратится.
- Приз и дневная квота — разные вещи: пул `used_units` в `billing/balance`
  отражает именно приз.
- Доступ к призу есть только у клиента ZCode (приложение или пропатченный CLI).
  Обычный API-ключ на `api.z.ai` приз не расходует — он относится к личному
  coding plan.
- Доказательство расхода — не экран подписки, а два факта вместе: `used_units`
  вырос и в rollout-файле `~/.zcode/cli/rollout/*.jsonl` стоит
  `"providerId":"account:zai-start-plan"`.

## Проверка одним запросом

```bash
python3 scripts/check-balance.py
```

Скрипт расшифровывает `zcodejwttoken` из локального стора ZCode, добавляет
`app_version` и `device_mid` (без них эндпоинт отвечает `400 parameter error`)
и печатает `used_units` / `remaining_units` по каждой позиции.

## Переключение модели

```bash
node scripts/set-start-plan-default.mjs GLM-5.3-Flash   # --dry, --clear
```

Пишет `defaultModelSelection` в обёртку `config` файла `~/.zcode/v2/provider_config.json`
(на верхнем уровне этого ключа нет) и делает бэкап `.bak-<дата>`.
