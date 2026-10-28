# Tech debt: paper-review-claude-port

- PORT-1: ДИАГНОЗ ЗАКРЫТ (2026-10-25). Плагин `paper-review.system.v2` **реально загружается и
  регистрируется** в работающем рантайме десктопа 2.0.32:
  - лог opencode: `loading plugin id="E:...paper-review-plugin/dist-v2/v2"` 07:28:03Z БЕЗ
    последующего `failed to load plugin` (все глобальные npm-плагины падают с LoadError — не наши);
  - `opencode plugin list` из каталога harness показывает `paper-review.system.v2 local`;
  - runtime-хранилище (БД kv): `plugin:paper-review.system.v2:paper-review.deps =
    {ok:true, checked_at:07:28:15Z}` — запись создал сам `setup()` через `ctx.storage.set(...)`,
    т.е. setup выполнился, check-deps прошёл.
  Хук `ctx.session.hook("context", ...)` — это ДОКУМЕНТИРОВАННЫЙ V2 API (раздел Build plugins →
  Hooks → Sessions → Model requests), сигнатура `event.system.push({type:"text",text})` точь-в-точь
  как в доке; переводить на `session.created` НЕ нужно (это событие, а не хук, у него другой payload).
  Также 2026-10-25 включено логирование setup в index.js ([paper-review] setup ok/failed +
  hook push/dispose) вместо полного глушения — неопределённость «регистрируется ли хук» теперь
  видна в opencode.log. node --check exit=0, check-deps --json all_required_ok=true.
- PORT-2: `{env:VAR}` подстановки в `environment` MCP `academic-search` при пустых
  переменных окружения дадут пустые значения; сервер это терпит (ключи опциональны),
  но при недоступности сети (429/202) сетевые тесты плагина остаются внешним ограничением.
- PORT-3: в `dist-v2/v2/index.js` отсутствует timeout у probe-вызова check-deps;
  для короткого детерминированного скрипта это приемлемо, но при заблокированном python
  setup-хук мог бы зависнуть — зафиксировано в reviewer-замечаниях.
- ROOT-CAUSE «плагин не виден в настройках десктопа»: плагин зарегистрирован в ПРОЕКТНОМ
  конфиге `E:\opencode_harness_portable\.opencode\opencode.json` (ключ `plugin`). Проектные
  конфиги opencode применяются только когда активный проект/каталог — harness. Десктоп в
  момент проверки работал с проектом `F:\1` (все активные сессии proj=F:/1; API
  `plugin.list` отдаёт location=C:\Users\Arhys) — там проектный конфиг harness не применяется,
  поэтому в Settings → Plugins бумажного плагина нет и не будет. Это ожидаемый скоуп
  project-конфигов, а не поломка интеграции. Чтобы плагин появился в настройках — открыть в
  десктопе проект `E:\opencode_harness_portable` (там же команды /review-paper, агенты, MCP).