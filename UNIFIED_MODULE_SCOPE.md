# Unified Module Scope

Этот модуль **не ограничивается фабрикой кода**. Он собирает в одном переносимом слое все системные компоненты OpenCode-оркестрации:

- agents
- shared process docs
- deterministic runtime scripts
- policy config
- memory / retrospective rules
- guard and trust boundaries
- environment / runtime wiring
- MCP servers and launchers
- skill modules
- routing / hooks / contracts / templates
- task / doc / debt controllers

## Подсистемы

| Подсистема | Назначение |
|---|---|
| Agents | UI-facing orchestration shells |
| Runtime scripts | state, validation, budget, stop criteria |
| Shared process | общая методология агентов |
| Policy | thresholds, strictness, routing, heuristics |
| Memory | retrospective and routing memory |
| Guard | injection/trust-boundary protection |
| Environment | cross-platform paths and env contract |
| MCP | execution perimeter to tools/services |
| Skills | domain/procedure modules |
| Controllers | task/doc/debt/global status control |

## Skills are first-class modules

`W:\server2\skills` содержит **184 skill modules**. Это отдельный capability layer, а не просто справочник.

## Memory is part of the module

Память — advisory subsystem. Она хранит lessons/patterns/route caveats, но не authoritative state.

## Policy is part of the module

Любая цифра, лимит, retry, threshold, strictness и stop-condition должны жить в versioned config, а не в prompt или разрозненных md.

## Guard is base runtime

Guard обязателен для code/research/writing orchestration whenever появляется untrusted context.

## MCP is execution perimeter

MCP layer должен иметь такие же явные contracts/guard semantics, как skill layer.
