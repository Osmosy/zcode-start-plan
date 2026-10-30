#!/usr/bin/env node
// Ставит defaultModelSelection в ~/.zcode/v2/provider_config.json на Start Plan.
// Файл общий для приложения ZCode и CLI, поэтому смена видна обоим.
//
//   node scripts/set-start-plan-default.mjs                       # GLM-5.3, reasoning high
//   node scripts/set-start-plan-default.mjs GLM-5.3-Flash         # Flash, reasoning high
//   node scripts/set-start-plan-default.mjs GLM-5.3 none          # без reasoning
//   node scripts/set-start-plan-default.mjs --dry                 # только показать, что будет
//   node scripts/set-start-plan-default.mjs --clear               # вернуть прежнее поведение (null)
//
// Перед сменой делает бэкап provider_config.json.bak-<дата>, как в docs/howto.md.

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const args = process.argv.slice(2).filter((a) => a !== '--dry');
const dry = process.argv.includes('--dry');
const clear = process.argv.includes('--clear');
const modelId = args[0] ?? 'GLM-5.3';
const reasoning = args[1] ?? 'high';

const cfgPath =
  process.env.ZCODE_PROVIDER_CONFIG ??
  path.join(os.homedir(), '.zcode/v2/provider_config.json');

if (!fs.existsSync(cfgPath)) {
  console.error(`нет файла ${cfgPath} — сначала запустить приложение ZCode хотя бы раз`);
  process.exit(1);
}

const raw = fs.readFileSync(cfgPath, 'utf8');
let cfg;
try {
  cfg = JSON.parse(raw);
} catch (e) {
  console.error(`provider_config.json не разбирается как JSON: ${e.message}`);
  process.exit(1);
}

const prev = cfg.defaultModelSelection ?? null;
const next = clear
  ? null
  : {
      providerId: 'account:zai-start-plan',
      modelId,
      ...(reasoning === 'none' ? {} : { options: { reasoningLevel: reasoning } }),
    };

console.log('файл  :', cfgPath);
console.log('было  :', JSON.stringify(prev));
console.log('станет:', JSON.stringify(next));

if (dry) {
  console.log('--dry: ничего не записано');
  process.exit(0);
}

if (JSON.stringify(prev) === JSON.stringify(next)) {
  console.log('уже стоит — правка не нужна');
  process.exit(0);
}

const bak = `${cfgPath}.bak-${new Date().toISOString().slice(0, 10)}`;
fs.writeFileSync(bak, raw);
if (next === null) delete cfg.defaultModelSelection;
else cfg.defaultModelSelection = next;
fs.writeFileSync(cfgPath, `${JSON.stringify(cfg, null, 2)}\n`);
console.log('бэкап :', bak);
console.log('записано');
