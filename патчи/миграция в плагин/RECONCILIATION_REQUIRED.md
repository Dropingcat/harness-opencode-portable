# Reconciliation Required

Следующие historical TD нельзя автоматически считать ни открытыми, ни закрытыми без проверки exact release tree:

- TD-002 Legacy plugin hook registration;
- TD-003 JSON/TS route duplication;
- TD-004 legacy OpenCode session DB guard requirement;
- TD-005 source-fetcher fallback;
- TD-006 presence/authority of config/tech_debt.json;
- TD-007 canonical documentation index;
- TD-008 WP-0 JSON Schema coverage;
- TD-014 manifest freshness.

## Procedure

1. Найти точный файл/контракт в текущем checkout.
2. Найти machine consumer и acceptance.
3. Если проблема устранена в рамках более нового TD, закрыть историческую запись с explicit relation `superseded_by`/`closed_by`.
4. Не merge ID задним числом.
5. Сохранить исходный title/status/source.
