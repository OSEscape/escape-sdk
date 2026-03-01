"""Execute CS2 client scripts via runScript."""

from __future__ import annotations

from escape._proto.bridge.v1 import bridge_pb2  # pyright: ignore[reportMissingImports]
from escape._services import Services


def run_script(
    script_id: int,
    *args: int | str,
    int_result_count: int = 0,
    string_result_count: int = 0,
) -> tuple[list[int], list[str]]:
    """Execute a CS2 client script.

    Args:
        script_id: The script ID to execute.
        *args: Script arguments — only int and str are valid (CS2 VM constraint).
        int_result_count: How many ints to read from the int stack after execution.
        string_result_count: How many strings to read from the string stack after execution.

    Returns:
        Tuple of (int_results, string_results) read from the VM stacks.
    """
    s = Services.get()

    proto_args = []
    for arg in args:
        if isinstance(arg, int):
            proto_args.append(bridge_pb2.ScriptArg(int_value=arg))
        else:
            proto_args.append(bridge_pb2.ScriptArg(string_value=str(arg)))

    resp = s.stub.RunScript(
        bridge_pb2.RunScriptRequest(
            script_id=script_id,
            args=proto_args,
            int_result_count=int_result_count,
            string_result_count=string_result_count,
        )
    )

    return list(resp.int_results), list(resp.string_results)
