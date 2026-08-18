"""
/sh   - Live streaming shell executor. Owner + Sudo users only.
/cmd  - Same as /sh, full access. Owner + Sudo users only.
"""
import asyncio
import time
from html import escape

from pyrogram import filters, types, enums
from Dev import app, config

# Premium custom emoji IDs
EMOJI_BOLT   = "5971801057540443125"   # processing / running
EMOJI_CHECK  = "5021905410089550576"   # success
EMOJI_ERROR  = "5420323339723881652"   # error / cross
EMOJI_WARN   = "5273914604752216432"   # warning
EMOJI_OUTPUT = "6181345004309451395"   # output / search
EMOJI_LOCK   = "5472164874886846699"   # locked / access denied


def _e(eid: str, fallback: str) -> str:
    return f"<emoji id='{eid}'>{fallback}</emoji>"


def _header(cmd: str) -> str:
    return (
        f"{_e(EMOJI_BOLT, '⏳')} <b>Shell Executor</b>\n"
        f"<blockquote><b>›</b> <code>{escape(cmd)}</code>\n"
        "Running...</blockquote>"
    )


def _format_output(cmd: str, stdout: str, stderr: str, exit_code: int, elapsed: float) -> str:
    ok = exit_code == 0
    icon = _e(EMOJI_CHECK, "✅") if ok else _e(EMOJI_ERROR, "❌")
    status = "Success" if ok else f"Failed (exit {exit_code})"

    parts = [
        f"{icon} <b>Shell Executor</b>",
        f"<blockquote><b>›</b> <code>{escape(cmd)}</code>\n"
        f"<b>Status:</b> {status}  |  <b>Time:</b> <code>{elapsed:.2f}s</code></blockquote>",
    ]

    if stdout.strip():
        out = stdout.strip()
        if len(out) > 3000:
            out = out[:3000] + "\n... (truncated)"
        parts.append(
            f"{_e(EMOJI_OUTPUT, '📄')} <b>Output:</b>\n"
            f"<blockquote expandable>{escape(out)}</blockquote>"
        )

    if stderr.strip():
        err = stderr.strip()
        if len(err) > 1500:
            err = err[:1500] + "\n... (truncated)"
        parts.append(
            f"{_e(EMOJI_WARN, '⚠️')} <b>Stderr:</b>\n"
            f"<blockquote expandable>{escape(err)}</blockquote>"
        )

    if not stdout.strip() and not stderr.strip():
        parts.append("<i>(no output)</i>")

    return "\n".join(parts)


def _format_chunk(cmd: str, live_out: str) -> str:
    out = live_out.strip()
    if len(out) > 2800:
        out = "..." + out[-2800:]
    return (
        f"{_e(EMOJI_BOLT, '⏳')} <b>Shell Executor</b>  <i>live</i>\n"
        f"<blockquote expandable><b>›</b> <code>{escape(cmd)}</code>\n\n"
        f"{escape(out) if out else 'Waiting for output...'}</blockquote>"
    )


async def _run_shell(cmd: str, sent, m: types.Message):
    """Core shell runner — shared by /sh and /cmd."""
    start_time = time.time()
    live_output = []
    last_edit = time.time()
    EDIT_INTERVAL = 2.5

    try:
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        async def read_stdout():
            nonlocal last_edit
            async for line in process.stdout:
                live_output.append(line.decode(errors="replace"))
                now = time.time()
                if now - last_edit >= EDIT_INTERVAL:
                    last_edit = now
                    try:
                        await sent.edit_text(
                            _format_chunk(cmd, "".join(live_output)),
                            parse_mode=enums.ParseMode.HTML,
                        )
                    except Exception:
                        pass

        await asyncio.gather(read_stdout(), asyncio.shield(process.wait()))

        stderr_bytes = await process.stderr.read()
        stderr_text  = stderr_bytes.decode(errors="replace")
        stdout_text  = "".join(live_output)
        exit_code    = process.returncode or 0
        elapsed      = time.time() - start_time

        await sent.edit_text(
            _format_output(cmd, stdout_text, stderr_text, exit_code, elapsed),
            parse_mode=enums.ParseMode.HTML,
        )

    except asyncio.CancelledError:
        await sent.edit_text(
            f"{_e(EMOJI_WARN, '🚫')} <b>Shell Executor</b>\n"
            f"<blockquote><code>{escape(cmd)}</code>\nCancelled.</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception as e:
        await sent.edit_text(
            f"{_e(EMOJI_ERROR, '💥')} <b>Shell Executor</b>\n"
            f"<blockquote><code>{escape(cmd)}</code>\n\n"
            f"<b>Exception:</b>\n{escape(str(e))}</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )


def _is_authorized(m: types.Message) -> bool:
    """Returns True if the sender is owner or a sudo user."""
    uid = m.from_user.id
    if uid == config.OWNER_ID:
        return True
    try:
        return uid in app.sudoers._user_ids
    except Exception:
        return False


_ACCESS_DENIED = (
    f"<emoji id='5472164874886846699'>🔒</emoji> <b>Access Denied</b>\n\n"
    "<blockquote>This command is restricted to <b>Owner</b> and <b>Sudo users</b> only.</blockquote>"
)

_USAGE = (
    f"<emoji id='5971801057540443125'>⚡</emoji> <b>Shell Executor</b>\n\n"
    "<blockquote><b>Usage:</b> <code>/{cmd} [command]</code>\n"
    "<b>Example:</b> <code>/{cmd} ls -la</code></blockquote>"
)


@app.on_message(filters.command(["sh", "shell"]))
async def shell_runner(_, m: types.Message):
    if not _is_authorized(m):
        return await m.reply_text(_ACCESS_DENIED, parse_mode=enums.ParseMode.HTML)

    if len(m.command) < 2:
        return await m.reply_text(
            _USAGE.format(cmd="sh"),
            parse_mode=enums.ParseMode.HTML,
        )

    cmd = m.text.split(maxsplit=1)[1]
    sent = await m.reply_text(_header(cmd), parse_mode=enums.ParseMode.HTML)
    await _run_shell(cmd, sent, m)


@app.on_message(filters.command(["cmd"]))
async def cmd_runner(_, m: types.Message):
    if not _is_authorized(m):
        return await m.reply_text(_ACCESS_DENIED, parse_mode=enums.ParseMode.HTML)

    if len(m.command) < 2:
        return await m.reply_text(
            _USAGE.format(cmd="cmd"),
            parse_mode=enums.ParseMode.HTML,
        )

    cmd = m.text.split(maxsplit=1)[1]
    sent = await m.reply_text(_header(cmd), parse_mode=enums.ParseMode.HTML)
    await _run_shell(cmd, sent, m)
