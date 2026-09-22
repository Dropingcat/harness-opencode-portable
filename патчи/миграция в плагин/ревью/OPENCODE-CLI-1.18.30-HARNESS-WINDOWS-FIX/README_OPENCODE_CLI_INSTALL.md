# OpenCode CLI 1.18.30 for Harness on Windows

Installs a pinned, isolated OpenCode CLI next to the Harness. It does not modify OpenCode Desktop.

Default root:

`C:\Temp\opencode\harness-deploy`

Run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\INSTALL_OPENCODE_CLI_1_18_30_WINDOWS.ps1
```

Persist only `OPENCODE_BIN` in the user environment:

```powershell
.\INSTALL_OPENCODE_CLI_1_18_30_WINDOWS.ps1 -PersistUserEnv
```

The helper:

1. checks `node` and `npm`;
2. installs `opencode-ai@1.18.30` under `.tools\opencode-cli-1.18.30`;
3. locates the real Windows native `opencode.exe`, including the platform package fallback;
4. accepts only version `1.18.30`;
5. checks `--version`, `--help`, and `run --help`;
6. sets the current session's `OPENCODE_BIN`;
7. writes `opencode_cli_install_status.json`.

No API keys or provider credentials are written.

Afterward:

```powershell
& $env:OPENCODE_BIN --version
& $env:OPENCODE_BIN models
```

If no model/provider is configured, authenticate/configure the CLI host-locally, then rerun the Harness remote acceptance protocol.
