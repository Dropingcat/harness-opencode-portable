# Dynamic Agent Prompt — {agent} (model: {model})

<!-- Generated context block by runtime/prompt_render.py from templates/agent_prompts/base.md.
     Роль-специфичная часть промпта — в agents/{agent}.md (системный промпт агента OpenCode).
     Этот блок подставляется Core при harness.run как контекст сессии. -->

## Session context

- **Task**: {task}
- **Workspace**: {workspace}
- **Route**: {route}
- **Capsules**: {capsules}
- **Skills**: {skills}
- **Tools**: {tools}

## Memory context

{memory_context}

## Role contracts (input/output obligations)

{contracts}

## Route hint

{agent_hint}
