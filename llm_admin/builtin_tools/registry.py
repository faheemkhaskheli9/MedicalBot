import importlib
from typing import Callable


BUILTIN_TOOL_REGISTRY: dict[str, Callable] = {}


def _load_builtin(dotted_path: str) -> Callable:
    module_path, _, func_name = dotted_path.rpartition(".")
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


def execute_tool(name: str, tool_type: str, implementation: str, params: dict) -> str:
    """
    Dispatch a tool call.

    - built_in / custom_python: resolve `implementation` as a dotted Python path and call it.
    - llm_subagent: call the linked LLMModel and return its text reply.
    """
    if tool_type in ("built_in", "custom_python"):
        if not implementation:
            return f"Error: tool '{name}' has no implementation path configured."
        fn = _load_builtin(implementation)
        return fn(**params)

    if tool_type == "llm_subagent":
        # params should contain {"messages": [...]} or {"prompt": "..."}
        return _run_llm_subagent(name, params)

    return f"Error: unknown tool_type '{tool_type}'"


def _run_llm_subagent(tool_name: str, params: dict) -> str:
    from llm_admin.models import Tool
    from llm_admin.providers import get_client

    tool_obj = Tool.objects.filter(name=tool_name, tool_type="llm_subagent").first()
    if not tool_obj or not tool_obj.llm_model:
        return f"Error: LLM subagent tool '{tool_name}' is not properly configured."

    client = get_client(tool_obj.llm_model)
    messages = params.get("messages") or [{"role": "user", "content": params.get("prompt", "")}]
    return client.complete(messages)
