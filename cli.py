import asyncio
import json
from uuid import UUID

import httpx
from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt

# API Configuration
API_BASE = "http://127.0.0.1:8000/api/v1"

# Same defaults packages/api/dependencies.py falls back to when a
# request omits the tenant/user headers entirely — using them here
# too means a document uploaded via curl/the browser with no explicit
# X-Tenant-ID/X-User-ID header lands in the same tenant this CLI talks
# to by default, instead of two random UUIDs that never overlap.
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000002"

console = Console()


def _ask_uuid(prompt: str, default: str) -> str:
    """
    Re-prompts until the input is a real UUID instead of sending
    whatever was typed straight to the server as a header — a stray
    keystroke here previously surfaced as a confusing `400 — X-User-ID
    must be a valid UUID` error several steps later, deep inside a
    chat request, rather than being caught where it was actually typed.
    """

    while True:
        value = Prompt.ask(prompt, default=default)
        try:
            UUID(value)
            return value
        except ValueError:
            console.print(f"[red]'{value}' isn't a valid UUID - try again.[/red]")


async def main():
    console.print("[bold green]Welcome to EasyDev AI CLI Tester[/bold green]")
    console.print("Make sure your uvicorn server is running on http://127.0.0.1:8000")

    tenant_id = _ask_uuid(
        "Enter Tenant ID (must match whatever tenant your documents were uploaded under)",
        DEFAULT_TENANT_ID,
    )
    user_id = _ask_uuid("Enter User ID", DEFAULT_USER_ID)

    headers = {
        "X-Tenant-ID": tenant_id,
        "X-User-ID": user_id,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(base_url=API_BASE, headers=headers, timeout=60.0) as client:
        try:
            health = await client.get("/health")
            if health.status_code == 200:
                console.print("[green]Server is healthy![/green]")
            else:
                console.print(f"[red]Server health check failed: {health.status_code}[/red]")
        except Exception as e:
            console.print(f"[red]Could not connect to server: {e}[/red]")
            return

        conversation_id = None
        while True:
            raw = Prompt.ask(
                "Enter a Conversation ID to resume or create one, or press Enter to "
                "start/continue this tenant+user's default conversation",
                default="",
            ).strip()
            if not raw:
                break
            try:
                UUID(raw)
                conversation_id = raw
                break
            except ValueError:
                console.print(f"[red]'{raw}' isn't a valid UUID - try again, or press Enter to skip.[/red]")

        # Streaming is the default now, not a per-run prompt — previously
        # this hardcoded "stream": False unconditionally, so the server's
        # SSE path (POST /chat with stream: true, packages/api/routers/
        # chat.py::_sse_events) was never reachable from this CLI at all.
        use_streaming = True

        console.print(f"Tenant: [cyan]{tenant_id}[/cyan]  User: [cyan]{user_id}[/cyan]")
        console.print(
            f"Conversation: [cyan]{conversation_id or '(default, auto-created/reused)'}[/cyan]"
        )
        console.print("Type 'exit' or 'quit' to stop.\n")

        while True:
            user_input = Prompt.ask("[bold blue]You[/bold blue]")

            if user_input.lower() in ("exit", "quit"):
                break

            if not user_input.strip():
                continue

            payload = {
                "conversation_id": conversation_id,
                "message": user_input,
                "stream": use_streaming,
            }

            if use_streaming:
                conversation_id = await _send_streaming(client, payload, conversation_id, console)
            else:
                conversation_id = await _send_blocking(client, payload, conversation_id, console)


async def _send_blocking(client, payload, conversation_id, console) -> str | None:
    with console.status("[bold yellow]AI is thinking...[/bold yellow]"):
        try:
            response = await client.post("/chat", json=payload)

            if response.status_code == 200:
                data = response.json()
                chat_data = data.get("data", {})
                reply = chat_data.get("response", "")

                # The server auto-creates a conversation on the first turn
                # when none was given — remember its ID so the rest of this
                # session's turns stay in the same conversation instead of
                # getting a fresh one each time.
                conversation_id = chat_data.get("conversation_id", conversation_id)

                console.print("\n[bold purple]EasyDev AI[/bold purple]")
                console.print(Markdown(reply))

                citations = chat_data.get("citations") or []
                if citations:
                    console.print("[dim]Citations:[/dim]")
                    for c in citations:
                        console.print(
                            f"[dim]  - document {c['document_id']} "
                            f"chunk #{c['chunk_index']} (score {c['score']:.2f})[/dim]"
                        )
                console.print()
            else:
                console.print(f"\n[red]Error {response.status_code}:[/red] {response.text}\n")

        except Exception as e:
            console.print(f"\n[red]Request failed:[/red] {e}\n")

    return conversation_id


async def _send_streaming(client, payload, conversation_id, console) -> str | None:
    """
    Reads the server's SSE stream (packages/api/routers/chat.py's
    "token"/"done" events) and prints each token as it arrives instead
    of waiting for the full reply. Note: the streaming path doesn't
    carry citations (a documented gap — SSE would need a second event
    type to carry them), so none are shown here even if retrieval ran.
    """

    console.print("\n[bold purple]EasyDev AI[/bold purple]")

    try:
        async with client.stream("POST", "/chat", json=payload) as response:
            if response.status_code != 200:
                body = await response.aread()
                console.print(f"\n[red]Error {response.status_code}:[/red] {body.decode()}\n")
                return conversation_id

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue

                event = json.loads(line[len("data: "):])

                if event.get("type") == "token":
                    console.print(event["content"], end="")
                elif event.get("type") == "done":
                    conversation_id = event.get("conversation_id", conversation_id)

    except Exception as e:
        console.print(f"\n[red]Request failed:[/red] {e}\n")
        return conversation_id

    console.print("\n")
    return conversation_id


if __name__ == "__main__":
    asyncio.run(main())
