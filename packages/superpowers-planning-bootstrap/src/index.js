export const PLANNING_MARKER = "[harness-superpowers-planning:v1]"

export const PLANNING_POLICY = `${PLANNING_MARKER}
Общий рабочий цикл для основных агентов и субагентов. Он дополняет роль,
а не заменяет её: соблюдай выданный контракт, разрешения и формат ответа.

Перед действием определи цель, ожидаемый результат, проверку готовности
и ограничения. Простой запрос не требует длинного плана или отдельного файла.
Загружай подходящие навыки через skill по точному ID из доступного списка;
не перезагружай уже присутствующий навык без необходимости.

PLAN → ACT → CHECK → DONE. Если проверка не пройдена или ты не можешь
обосновать следующий шаг, вернись в PLAN с конкретным затруднением.
Не жди словесного триггера от пользователя. Различай временную ошибку
(ограниченный повтор/другой способ), недостаток сведений (поиск/проверка)
и слишком крупную задачу (проверяемые подзадачи). Ожидаемый провал теста
в RED-фазе TDD сам по себе не требует перепланирования.

Каждая подзадача проходит тот же цикл. Родитель переходит в WAIT_CHILDREN,
после их завершения собирает результат и выполняет собственный CHECK.
Не называй родителя DONE только потому, что завершились его подзадачи.
Сохраняй уже сделанное; перепланируй остаток. Не повторяй отвергнутый
подход без новых оснований. Учитывай лимиты шагов, попыток и ресурсов;
при отсутствии разрешённого пути или исчерпании лимита сообщи BLOCKED.

Если задача уже задана контрактом родителя, не начинай заново обсуждение
всего проекта, согласование дизайна или рекурсивный диспатч. Подзадачи
можно выполнить самому; делегировать можно только при разрешении.
Для научной работы проверки — источники, допущения и корректность вывода,
а не механический перенос кодовых TDD/commit/worktree на любой текст.

Не ослабляй критерии готовности, не расширяй доступ и не меняй формат
итогового JSON/отчёта ради этого цикла. Не печатай служебную карточку
или подробные внутренние рассуждения вместо требуемого результата.
Это инструкция самоконтроля, не утверждение о наличии внешнего
детектора мыслей, автоматической проверки или сохранённой памяти.
`

export function createPlanningPlugin(upstream) {
  if (upstream?.id !== "superpowers" || typeof upstream.setup !== "function") {
    throw new Error("Expected the reviewed Superpowers V2 plugin definition")
  }
  return {
    id: "harness.superpowers.planning",
    async setup(ctx) {
      if (typeof ctx.session?.hook !== "function" || typeof ctx.skill?.transform !== "function") {
        throw new Error("Superpowers planning bootstrap requires OpenCode V2")
      }
      const registrations = []
      const sessions = new Map()
      let closed = false
      const own = registration => {
        if (typeof registration?.dispose === "function") registrations.push(registration)
        return registration
      }
      const cleanup = async () => {
        if (closed) return
        closed = true
        sessions.clear()
        for (const registration of registrations.reverse()) {
          try { await registration.dispose() }
          catch { console.error("[superpowers-planning] registration cleanup failed") }
        }
      }
      const getSession = async ({ sessionID }) => {
        if (typeof sessionID !== "string" || !sessionID) throw new Error("Missing session identity")
        if (sessions.has(sessionID)) return sessions.get(sessionID)
        const result = await ctx.session.get({ sessionID })
        const session = result && "data" in result ? result.data : result
        if (result?.error != null || result?.response?.ok === false || session?.id !== sessionID ||
            (session.parentID !== undefined && (typeof session.parentID !== "string" || !session.parentID))) {
          throw new Error("Session identity could not be verified")
        }
        const identity = { id: sessionID, ...(session.parentID === undefined ? {} : { parentID: session.parentID }) }
        if (sessions.size >= 256) sessions.delete(sessions.keys().next().value)
        sessions.set(sessionID, identity)
        return identity
      }
      const protectedContext = {
        ...ctx,
        session: {
          ...ctx.session,
          get: getSession,
          hook: async (name, callback, options) => own(await ctx.session.hook(name, async event => {
            if (name === "context") {
              if (!event.agent) return
              try {
                const session = await getSession({ sessionID: event.sessionID })
                // Hold the decision in this request: another session can evict
                // the cache before upstream performs its own second lookup.
                if (session.parentID !== undefined) return
              }
              catch {
                console.warn("[superpowers-planning] controller bootstrap deferred: session identity unavailable")
                return
              }
            }
            return callback(event)
          }, options)),
        },
        skill: {
          ...ctx.skill,
          transform: async callback => own(await ctx.skill.transform(editor => callback(new Proxy(editor, {
            get(target, key) {
              if (key === "add") return skill => {
                if (!target.get(skill.id)) target.add(skill)
              }
              const value = Reflect.get(target, key, target)
              return typeof value === "function" ? value.bind(target) : value
            },
          })))),
        },
      }
      try {
        const upstreamCleanup = await upstream.setup(protectedContext)
        if (typeof upstreamCleanup === "function") own({ dispose: upstreamCleanup })
        own(await ctx.session.hook("context", event => {
          if (!event.agent || !Array.isArray(event.system)) return
          if (event.system.some(part => part.type === "text" && part.text?.includes(PLANNING_MARKER))) return
          event.system.push({ type: "text", text: PLANNING_POLICY })
        }))
        return cleanup
      } catch (error) {
        await cleanup()
        throw error
      }
    },
  }
}
