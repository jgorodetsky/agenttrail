"""CLI entry point for agenttrail."""

from __future__ import annotations

import json
import sys

import anyio
import click


@click.group()
def main():
    """agenttrail - agent audit logging framework"""
    pass


@main.command()
@click.option("--name", required=True, help="name for this MCP server (e.g. filesystem, postgres)")
@click.option("--collector", default=None, help="collector URL (e.g. http://localhost:8100)")
@click.option("--log", default=None, help="local JSONL log path (fallback or additional)")
@click.argument("server_command", nargs=-1, required=True)
def proxy(name: str, collector: str | None, log: str | None, server_command: tuple[str, ...]):
    """start MCP audit proxy wrapping a server command"""
    from agenttrail.collectors.mcp.config import ProxyConfig
    from agenttrail.collectors.mcp.proxy import run_proxy

    if not collector and not log:
        log = f"audit-{name}.jsonl"

    config = ProxyConfig(
        server_command=list(server_command),
        server_name=name,
        collector_url=collector,
        local_log_path=log,
    )
    anyio.run(run_proxy, config)


@main.command("collector")
@click.option("--port", default=8100, help="port to listen on")
@click.option("--host", default="0.0.0.0", help="host to bind to")
@click.option(
    "--output", "outputs", multiple=True, help="output config (e.g. jsonl:./audit.jsonl, stdout, webhook:https://...)"
)
def collector_cmd(port: int, host: str, outputs: tuple[str, ...]):
    """start the central event collector"""
    import uvicorn

    from agenttrail.server.collector import app, configure_outputs

    output_instances = _parse_outputs(outputs or ("stdout",))
    configure_outputs(output_instances)

    uvicorn.run(app, host=host, port=port, log_level="info")


@main.group()
def hooks():
    """manage hooks-based collection (Claude Code, Cursor, etc.)"""
    pass


@hooks.command("install")
@click.option("--collector", default=None, help="collector URL (e.g. http://localhost:8100)")
@click.option("--log", default=None, help="local JSONL log path")
@click.option("--platform", default="claude-code", type=click.Choice(["claude-code"]), help="target platform")
def hooks_install(collector: str | None, log: str | None, platform: str):
    """install agenttrail hooks into agent runtime settings"""
    from agenttrail.collectors.hooks.install import install_claude_code

    if not collector and not log:
        log = "~/.agenttrail/audit.jsonl"

    path = install_claude_code(collector_url=collector, log_path=log)
    click.echo(f"installed agenttrail hooks in {path}")
    click.echo("all tool calls will now emit OCSF audit events")


@hooks.command("uninstall")
@click.option("--platform", default="claude-code", type=click.Choice(["claude-code"]), help="target platform")
def hooks_uninstall(platform: str):
    """remove agenttrail hooks from agent runtime settings"""
    from agenttrail.collectors.hooks.install import uninstall_claude_code

    path = uninstall_claude_code()
    click.echo(f"removed agenttrail hooks from {path}")


@hooks.command("handler")
@click.option("--collector", default=None, help="collector URL", envvar="AGENTTRAIL_COLLECTOR_URL")
@click.option("--log", default=None, help="local JSONL log path", envvar="AGENTTRAIL_LOG_PATH")
def hooks_handler(collector: str | None, log: str | None):
    """handle a hook event from stdin (called by agent runtime)"""
    from agenttrail.collectors.hooks.handler import run_handler

    run_handler(collector_url=collector, log_path=log)


@main.command()
def schema():
    """print the JSON Schema for audit events"""
    from agenttrail.schema.event import ToolCallEvent

    click.echo(json.dumps(ToolCallEvent.model_json_schema(), indent=2))


@main.command()
@click.argument("file", type=click.Path(exists=True))
def validate(file: str):
    """validate a JSONL file against the audit event schema"""
    errors = 0
    total = 0
    with open(file) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                event = json.loads(line)
                if "class_uid" not in event:
                    click.echo(f"line {line_num}: missing class_uid (not OCSF format)")
                    errors += 1
                elif event.get("class_uid") != 6003:
                    click.echo(f"line {line_num}: class_uid={event['class_uid']}, expected 6003")
                    errors += 1
            except json.JSONDecodeError as e:
                click.echo(f"line {line_num}: invalid JSON - {e}")
                errors += 1

    if errors:
        click.echo(f"\n{errors} errors in {total} events")
        sys.exit(1)
    else:
        click.echo(f"{total} events validated successfully")


def _parse_outputs(specs: tuple[str, ...]) -> list:
    from agenttrail.server.outputs.base import BaseOutput

    outputs: list[BaseOutput] = []
    for spec in specs:
        if spec == "stdout":
            from agenttrail.server.outputs.stdout import StdoutOutput

            outputs.append(StdoutOutput())
        elif spec.startswith("jsonl:"):
            from agenttrail.server.outputs.jsonl import JSONLOutput

            outputs.append(JSONLOutput(spec.split(":", 1)[1]))
        elif spec.startswith("webhook:"):
            from agenttrail.server.outputs.webhook import WebhookOutput

            outputs.append(WebhookOutput(spec.split(":", 1)[1]))
        elif spec.startswith("s3:"):
            from agenttrail.server.outputs.s3 import S3Output

            parts = spec.split(":", 1)[1]
            outputs.append(S3Output(bucket=parts))
        elif spec.startswith("sqs:"):
            from agenttrail.server.outputs.sqs import SQSOutput

            outputs.append(SQSOutput(queue_url=spec.split(":", 1)[1]))
        else:
            click.echo(f"unknown output: {spec}", err=True)
            sys.exit(1)
    return outputs


if __name__ == "__main__":
    main()
