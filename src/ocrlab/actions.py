"""One MCP tool per group of related tools.

Each tool takes an action name and that action's arguments, and calls the existing lab function unchanged. The tool's
description lists every action with its parameters, so a model sees the same facts the old separate tools gave it.
"""

import inspect
from typing import Annotated, Any, Callable, Literal, get_args, get_origin

from mcp.server.mcpserver.exceptions import ToolError


def _type_text(annotation) -> tuple[str, str]:
    """(type as text, description) of one parameter annotation."""
    desc = ""
    if get_origin(annotation) is Annotated:
        base, *meta = get_args(annotation)
        for m in meta:
            d = getattr(m, "description", None)
            if d:
                desc = d
        annotation = base
    if annotation is inspect.Parameter.empty:
        return "any", desc
    text = getattr(annotation, "__name__", None) if isinstance(annotation, type) else None
    return (text or str(annotation).replace("typing.", "")), desc


def params(fn: Callable) -> str:
    """The parameters as `name: type [description]`, with `?` after an optional name."""
    out = []
    for p in inspect.signature(fn).parameters.values():
        t, d = _type_text(p.annotation)
        opt = "" if p.default is inspect.Parameter.empty else "?"
        out.append(f"{p.name}{opt}: {t}" + (f" [{d}]" if d else ""))
    return ", ".join(out)


def describe(summary: str, actions: dict[str, Callable]) -> str:
    lines = [summary, "", "Pass `action` and that action's arguments in `args`. Actions:"]
    for name, fn in actions.items():
        doc = (inspect.getdoc(fn) or "").split("\n\n")[0].replace("\n", " ").strip()
        lines.append(f"- {name}({params(fn)}): {doc}")
    return "\n".join(lines)


def call(tool: str, actions: dict[str, Callable], action: str, args: dict[str, Any] | None) -> Any:
    fn = actions.get(action)
    if fn is None:
        raise ToolError(f"{tool}: unknown action {action!r}. Actions: {', '.join(actions)}")
    try:
        bound = inspect.signature(fn).bind(**(args or {}))
    except TypeError as e:
        raise ToolError(f"{tool}.{action}: {e}. Expected {action}({params(fn)})") from None
    return fn(*bound.args, **bound.kwargs)


def add_action_tool(server, name: str, summary: str, actions: dict[str, Callable]) -> None:
    names = tuple(actions)

    def run(action: str, args: dict[str, Any] | None = None) -> Any:
        return call(name, actions, action, args)

    run.__annotations__ = {"action": Literal[names], "args": dict[str, Any] | None, "return": Any}
    run.__name__ = name
    server.add_tool(run, name=name, description=describe(summary, actions), structured_output=False)
