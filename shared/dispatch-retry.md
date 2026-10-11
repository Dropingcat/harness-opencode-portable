# Dispatch Failure Recovery

> Retry protocol for sub-agent dispatch failures. **Include in any agent that dispatches sub-agents** — i.e. the Synthesizing Researcher.

opencode dispatches sub-agents with the `task` tool. The following are retryable:

- A `task` call times out or returns an error.
- A sub-agent returns an empty or "no response" final message.
- Rate-limit or transient provider errors surfacing in the sub-agent result.

**Retry protocol:**

1. Wait ~2 seconds, then retry the dispatch (same prompt + "This is retry attempt 1 of 3.").
2. If still failing, wait ~4 seconds, then retry (attempt 2 of 3).
3. If still failing, wait ~8 seconds, then retry (attempt 3 of 3).
4. After 3 failed attempts, **notify the user directly** — do not continue silently.

When retrying, re-send the same research prompt and add: "This is retry attempt N of 3."

---

## Empty Response Handling

If a sub-agent returns successfully but with an empty or "no response" final message:

1. **Check whether the work was completed** — opencode sub-agents communicate solely via their final message, and sub-agents in this project cannot write files. So an empty return means there is no usable report.
2. **If no usable report** — retry the dispatch (counts against the retry limit above), nudging the model to return its report as its final message.
3. **Log the empty-response pattern** for reflection in the synthesis summary.

This pattern occurs occasionally with some models that finish work but emit empty return messages. Because sub-agents here have no other side effects, an empty return means there is nothing to synthesize — retry promptly.
