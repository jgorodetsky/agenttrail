# Security policy

## Report a vulnerability

Report it privately through GitHub: open the **Security** tab and click **Report a vulnerability**, or go to https://github.com/jgorodetsky/agenttrail/security/advisories/new. Do not open a public issue.

Include the version, the steps to reproduce, and the impact. I aim to reply within 7 days.

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | yes |

## Scope

In scope:

- The hooks handler or MCP proxy changes, blocks or drops the agent's actions, or runs code from event content
- Events that are lost, altered or attributed to the wrong agent or session
- The collector or an output sending events somewhere other than the configured destination

Out of scope:

- What the monitored agent does. agenttrail records actions and does not block them.
