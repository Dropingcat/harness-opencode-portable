# Test and Evidence Matrix

## Evidence levels

- `VERIFIED_RELEASE` — сохранённый acceptance конкретной интегрированной поставки.
- `DEPLOYMENT_VERIFIED` — повторено на пользовательском deployment.
- `HOSTLESS_REPORTED` — plugin/bridge tests по актуализированной документации без настоящего OpenCode host.
- `LIVE_CERTIFIED` — проверено в настоящем поддерживаемом OpenCode host.
- `DESIGN_ONLY` — архитектура/план без заявления реализации.

| Утверждение | Уровень | Текущее evidence | Ограничение |
|---|---|---|---|
| Integrated Writer/Researcher/Coder работает как единый Harness | VERIFIED_RELEASE + DEPLOYMENT_VERIFIED | Writer 31+15, Researcher 588, Coder 5, integration 2 | Не доказывает live model execution |
| Researcher R4 deterministic contracts | VERIFIED_RELEASE | 111/111 PASS | Не калибрует scientific quality модели |
| Runtime/capability policy compilers | VERIFIED_RELEASE + DEPLOYMENT_VERIFIED | hashes сохранены | Не означает provider auth/readiness |
| Windows code-only distribution | DEPLOYMENT_VERIFIED | 2735 archive files byte-match; 0 content mismatch | reference filename decoding differences только legacy docs |
| Native Plugin P1 bridge/tools | HOSTLESS_REPORTED | reconciliation сообщает hostless Python + JS/Python PASS | Exact commit/tree и live Desktop не установлены |
| Native Plugin загружается в Desktop | PENDING | нет | DEV-03 / TD-057 |
| Real HostContext/WorkspaceRef | PENDING | нет live evidence | TD-057/063 scope distinction |
| semantic.execute read-only worker | PENDING | disabled/not certified | TD-058/059 |
| Tribunal через plugin | PENDING | process fixtures + CLI-oriented design only | TD-037/062 |
| Writer через generic semantic transport | PENDING | нет | TD-024/062 |
| Coder через generic semantic transport | PENDING | current semantic launchers legacy | TD-024/062 |
| HypothesisCase lifecycle | DESIGN_ONLY | architecture/virtual E2E design | TD-048 |
| Evidence independence | DESIGN_ONLY | architecture design | TD-049 |
| EvidenceDigest | DESIGN_ONLY | architecture design | TD-050 |

## Canonical saved baseline numbers

### Integrated release
- Writer: 31 tests + 15 subtests PASS
- Researcher full: 588/588 PASS
- Researcher R4: 111/111 PASS
- Coder: 5/5 PASS
- cross-module: 2/2 PASS
- compatibility groups observed: 136/136 PASS

### Policy hashes
- runtime: `8910fd61122b450212d5bc459cdb52acdc02aa3cf6d87a37c5eaa3778e3cdfef`
- capability: `60105d715f8df50917156216b085f85ee25a2b1deb62947e041bd8537a1a9076`

## Rule

Нельзя складывать hostless, focused subset и full-suite counts в одно число «всего тестов». Каждый результат относится к своей границе.
