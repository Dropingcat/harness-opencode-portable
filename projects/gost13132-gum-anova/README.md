# gost13132-gum-anova — директория артефактов проекта

Контракт 12 (`docs/CODERS/12_PROJECT_ARTIFACTS.md`), шаблон пути артефакта — контракт 10 §9.

## PROJECT_ID
`gost13132-gum-anova` (kebab-case)

## Цель
Единая изолированная директория артефактов проекта по ГОСТ EN 13132 (определение ГУМ / ANOVA-обработка
результатов межлабораторных испытаний), чтобы ролевые JSON звеньев цикла (worker/reviewer/auditor/analyst/
researcher/deployer) писались по шаблону 10 §9 без коллизий с другими проектами.

## Переменные (см. config.env)
| Переменная | Значение |
|---|---|
| HARNESS_ROOT | E:\opencode_harness_portable |
| PROJECT_ID | gost13132-gum-anova |
| PROJECT_ARTIFACTS | ${HARNESS_ROOT}/projects/gost13132-gum-anova/artifacts |
| PROJECT_RUNS | ${HARNESS_ROOT}/projects/gost13132-gum-anova/runs |
| PROJECT_REPORTS | ${HARNESS_ROOT}/projects/gost13132-gum-anova/reports |

## Правила
- Каждый проект = отдельная директория; артефакты разных проектов не смешиваются (контракт 12 §3).
- Артефакты звеньев: `artifacts/<ROLE>_<BLOCK_ID>.json` по шаблону контракта 10 §9 (git-версионируется).
  - ROLE ∈ {worker, reviewer, auditor, analyst, researcher, deployer}
  - BLOCK_ID — идентификатор блока (B1-T2, W1, EXP-1b, ...)
- Верификация: единые DoD-проверки (контракты 03-05), не зависящие от проекта.
- Рантайм (`runs/`, временные) — НЕ в git.
- Отчёты аналитика/журналы — в `reports/`.
- Кодировка файлов — UTF-8.

## Структура
```
projects/gost13132-gum-anova/
├── artifacts/      # <ROLE>_<BLOCK_ID>.json (git)
├── runs/           # рантайм (НЕ git)
├── reports/        # ANALYST_REPORTS, ORCHESTRATOR_NOTES
├── tech_debt.md    # TD-реестр проекта
├── README.md       # этот файл
└── config.env      # переменные проекта
```
