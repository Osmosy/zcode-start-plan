# NOTICE

This archive contains a patch to ZCode (https://github.com/zai-org/ZCode), commit
3c5b227649371507ddc4eb46ac5133afe6db1cab, licensed under the Apache License 2.0 (see LICENSE).
The patch is distributed under the same licence. It is not affiliated with or endorsed by Z.ai.

Files changed by the patch (changes are marked `Local patch` in the code):

- apps/zcode-cli/packages/bootstrap/src/app/standalone-account-provider-runtime.ts (modified):
  Start Plan in the standalone CLI catalog, entitlement from the ZCode JWT, model whitelist from
  ZCODE_STANDALONE_START_PLAN_MODELS or billing/balance, request authorisation with the JWT,
  diagnostics behind ZCODE_DEBUG_START_PLAN.
- packages/provider/src/model-selection-config.ts (modified): a default model selection saved
  without options is completed with the model's highest reasoning level instead of being dropped.
- apps/zcode-cli/packages/bootstrap/tests/standalone-start-plan.test.ts (new): tests for the above.
- packages/provider/test/model-selection-config.test.ts (modified): one test added.

## Дополнение (этот репозиторий)

- `patch/0001-start-plan.patch` — исходный патч из архива `zcode-start-plan-2026-10-24`,
  Apache-2.0, автор не аффилирован с Z.ai.
- `patch/0002-device-mid-and-retry.patch` — локальные правки поверх него: параметр
  `device_mid` в запросе `billing/balance` (без него 400 `parameter error`, из-за чего
  Start Plan молча не включается и запросы уходят на личный API-ключ) и три попытки
  запроса с паузой 1,5 с (эндпоинт периодически таймаутит). Распространяется на тех же
  условиях, что и `0001`.
- `docs/`, `scripts/` — без лицензионных ограничений сверх Apache-2.0.
- Ничего не отправляется на сторонние серверы: доступы читаются из локального стора
  ZCode (`~/.zcode/v2/credentials.json`).
