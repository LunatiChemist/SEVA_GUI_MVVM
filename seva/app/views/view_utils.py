from __future__ import annotations

from typing import Any, Callable, Optional


def safe_call(
    fn: Optional[Callable[..., Any]],
    *args: Any,
    on_error: Optional[Callable[[Exception], None]] = None,
) -> None:
    if fn is None:
        return
    try:
        fn(*args)
    except Exception as exc:
        if on_error:
            on_error(exc)
        else:
            print(f"Callback failed: {exc}")


__all__ = ["safe_call"]
