# REA Installation And Verification

Installed on 2026-10-12 using the published `rea-agents@6.4.0` package.

## Installed Integrations

| Client | Installation | Verification |
| --- | --- | --- |
| Claude Code | Personal MCP registration and personal skill | MCP initialization, 170 advertised tools, and a successful `binary_session` call |
| GitHub Copilot in VS Code | User-profile MCP registration and shared personal skill | MCP initialization, 170 advertised tools, and a successful `binary_session` call |
| GitHub Copilot CLI | Personal MCP registration and shared personal skill | MCP initialization, 170 advertised tools, and a successful `binary_session` call |

Existing Claude Code and VS Code configurations were backed up by the official installer. The test compared their parsed contents with the backups, excluding only the REA entry: unrelated configuration was preserved. Copilot CLI received a new configuration file.

The shared and Claude Code skill contents match, their YAML name is valid, and their referenced guides exist. No native decompiler, system runtime upgrade, credentials, or unrelated agent integration was installed.

## Use The Skill

1. In VS Code, run **Developer: Reload Window**, then open a new Copilot chat. Review any MCP trust/start prompt before approving the installed REA server.
2. Restart the Claude Code session so it discovers its new skill and MCP registration.
3. Invoke `/reverse-engineer-anything` with the target and the question. The same skill name applies in Copilot and Claude Code.

For example, ask REA to inspect the locally built MiroFish frontend and explain the report-generation API boundary. For an ordinary complete source repository, the skill deliberately routes the investigation to source inspection instead of native decompilation.

The tests launch the exact configured server commands directly. They do not establish that an already-open agent chat has reconnected or that the slash command has appeared in its UI.

## Rerun The Smoke Test

From this workspace:

```sh
node .rea/verify-install.mjs
```

The [smoke test](.rea/verify-install.mjs) reuses REA's cached package dependencies and speaks standard MCP JSON-RPC over stdio. It checks the skill, registrations, preserved configuration, tool discovery, and a real tool call for all three launchers. Its saved [verification result](.rea/verification.json) records the server versions and results without copying unrelated settings or credentials.

REA remains version-pinned and launches through `npx`; a standalone global `rea` executable was not installed. Clearing the npm cache means the launcher must download the package again, and the local smoke test needs the package to be cached first.

## MiroFish Investigation

The [reverse-engineering report](MIROFISH-REVERSE-ENGINEERING.md) combines source tracing with genuine REA analysis of the locally built frontend artifact. Its artifact coverage is explicitly partial because both bounded semantic-analysis passes exhausted their worker heaps.

To rebuild the artifact and repeat the capped analysis:

```sh
npm ci --prefix MiroFish/frontend --no-audit --no-fund
npm --prefix MiroFish/frontend run build
npx --yes rea-agents@6.4.0 analyze-javascript-application \
  "$PWD/MiroFish/frontend/dist" \
  --max-heap-mb 2048 --analysis-timeout-ms 120000 --format json
```

This does not run a simulation or call an LLM/Zep service. Native decompilation still requires a separately configured supported analysis engine.