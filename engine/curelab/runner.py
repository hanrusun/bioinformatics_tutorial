"""Run learner code in a persistent Jupyter kernel (IRkernel for R packs,
ipykernel for Python packs, ...)."""

from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from jupyter_client.manager import AsyncKernelManager

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)


@dataclass
class ExecResult:
    status: str = "ok"  # ok | error | timeout
    stdout: str = ""
    stderr: str = ""
    results: list[str] = field(default_factory=list)  # text/plain reprs of values
    images: list[str] = field(default_factory=list)  # base64 PNGs
    error: Optional[dict[str, Any]] = None  # {ename, evalue, traceback}
    elapsed: float = 0.0

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def error_text(self) -> str:
        if not self.error:
            return ""
        parts = [self.error.get("ename", ""), self.error.get("evalue", "")]
        parts += self.error.get("traceback", [])
        return "\n".join(p for p in parts if p)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "results": self.results,
            "images": self.images,
            "error": self.error,
            "elapsed": round(self.elapsed, 2),
        }


class KernelRunner:
    """A single kernel shared by the local player, with executions serialized."""

    def __init__(self, kernel_name: str, env: Optional[dict[str, str]] = None, cwd: Optional[str] = None):
        self.kernel_name = kernel_name
        self.env = env or {}
        self.cwd = cwd
        self.km: Optional[AsyncKernelManager] = None
        self.kc = None
        self._lock = asyncio.Lock()
        self.busy = False

    @property
    def started(self) -> bool:
        return self.km is not None and self.kc is not None

    async def start(self) -> None:
        if self.started:
            return
        km = AsyncKernelManager(kernel_name=self.kernel_name)
        env = {**os.environ, **self.env}
        kwargs: dict[str, Any] = {"env": env}
        if self.cwd:
            kwargs["cwd"] = self.cwd
        await km.start_kernel(**kwargs)
        kc = km.client()
        kc.start_channels()
        try:
            await kc.wait_for_ready(timeout=120)
        except Exception:
            kc.stop_channels()
            await km.shutdown_kernel(now=True)
            raise
        self.km, self.kc = km, kc

    async def restart(self) -> None:
        async with self._lock:
            await self._shutdown()
            await self.start()

    async def shutdown(self) -> None:
        async with self._lock:
            await self._shutdown()

    async def _shutdown(self) -> None:
        if self.kc is not None:
            self.kc.stop_channels()
        if self.km is not None:
            try:
                await self.km.shutdown_kernel(now=True)
            except Exception:  # pragma: no cover - best effort
                pass
        self.km = self.kc = None

    async def execute(self, code: str, timeout: float = 900.0) -> ExecResult:
        async with self._lock:
            if not self.started:
                await self.start()
            self.busy = True
            try:
                return await self._execute(code, timeout)
            finally:
                self.busy = False

    async def _execute(self, code: str, timeout: float) -> ExecResult:
        assert self.kc is not None and self.km is not None
        result = ExecResult()
        started = time.monotonic()
        deadline = started + timeout
        msg_id = self.kc.execute(code, store_history=False, allow_stdin=False, stop_on_error=True)
        stdout: list[str] = []
        stderr: list[str] = []
        timed_out = False
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            try:
                msg = await self.kc.get_iopub_msg(timeout=min(remaining, 1.0))
            except asyncio.TimeoutError:
                continue
            except Exception as exc:  # queue.Empty from some jupyter_client versions
                if exc.__class__.__name__ == "Empty":
                    if not await self.km.is_alive():
                        result.status = "error"
                        result.error = {"ename": "KernelDied", "evalue": "The kernel stopped unexpectedly.", "traceback": []}
                        await self._shutdown()
                        break
                    continue
                raise
            if msg.get("parent_header", {}).get("msg_id") != msg_id:
                continue
            mtype = msg["header"]["msg_type"]
            content = msg["content"]
            if mtype == "stream":
                (stdout if content.get("name") == "stdout" else stderr).append(content.get("text", ""))
            elif mtype in ("execute_result", "display_data"):
                data = content.get("data", {})
                if "image/png" in data:
                    result.images.append(data["image/png"].replace("\n", ""))
                elif "text/plain" in data:
                    result.results.append(strip_ansi(data["text/plain"]))
            elif mtype == "error":
                result.status = "error"
                result.error = {
                    "ename": content.get("ename", "Error"),
                    "evalue": strip_ansi(content.get("evalue", "")),
                    "traceback": [strip_ansi(t) for t in content.get("traceback", [])],
                }
            elif mtype == "status" and content.get("execution_state") == "idle":
                break
        if timed_out:
            result.status = "timeout"
            result.error = {
                "ename": "Timeout",
                "evalue": f"Execution took longer than {int(timeout)} seconds and was interrupted.",
                "traceback": [],
            }
            try:
                await self.km.interrupt_kernel()
                # drain until idle so the next execution starts clean
                drain_deadline = time.monotonic() + 15
                while time.monotonic() < drain_deadline:
                    try:
                        msg = await self.kc.get_iopub_msg(timeout=1.0)
                    except Exception:
                        continue
                    if (
                        msg.get("parent_header", {}).get("msg_id") == msg_id
                        and msg["header"]["msg_type"] == "status"
                        and msg["content"].get("execution_state") == "idle"
                    ):
                        break
                else:
                    await self._shutdown()
            except Exception:  # pragma: no cover
                await self._shutdown()
        result.stdout = strip_ansi("".join(stdout))
        result.stderr = strip_ansi("".join(stderr))
        result.elapsed = time.monotonic() - started
        return result
