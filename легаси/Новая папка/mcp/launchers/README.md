# OpenCode launcher MCPs

These launchers wrap `opencode run --pure` into narrowly scoped roles:

- code worker;
- web researcher;
- academic researcher;
- service worker;
- profile configurator.

Each launcher must keep a hard contract with:

- allowed actions;
- forbidden actions;
- output JSON schema;
- timeout;
- isolated run directory;
- no secrets in prompt/output.
