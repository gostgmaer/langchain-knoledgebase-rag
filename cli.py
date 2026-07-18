import asyncio
import uuid
import httpx
from rich.console import Console
from rich.prompt import Prompt
from rich.markdown import Markdown

# API Configuration
API_BASE = "http://127.0.0.1:8000/api/v1"
HEADERS = {
    "X-Tenant-Id": str(uuid.uuid4()), # Mock tenant ID
    "Content-Type": "application/json",
}

console = Console()

async def ensure_conversation(client: httpx.AsyncClient) -> str:
    # Normally we would hit POST /conversations here.
    # Since that endpoint isn't wired up yet, we'll try a dummy UUID.
    # If the backend requires the conversation to exist in the DB, this will 404.
    # In that case, we need to create it manually in the DB first.
    return "3fa85f64-5717-4562-b3fc-2c963f66afa6"

async def main():
    console.print("[bold green]Welcome to EasyDev AI CLI Tester[/bold green]")
    console.print("Make sure your uvicorn server is running on http://127.0.0.1:8000")
    
    async with httpx.AsyncClient(base_url=API_BASE, headers=HEADERS, timeout=60.0) as client:
        # Check health
        try:
            health = await client.get("/health")
            if health.status_code == 200:
                console.print("[green]Server is healthy![/green]")
            else:
                console.print(f"[red]Server health check failed: {health.status_code}[/red]")
        except Exception as e:
            console.print(f"[red]Could not connect to server: {e}[/red]")
            return

        conversation_id = Prompt.ask("Enter a Conversation ID (or press Enter for a default dummy UUID)", default="3fa85f64-5717-4562-b3fc-2c963f66afa6")
        
        console.print(f"Using conversation ID: [cyan]{conversation_id}[/cyan]")
        console.print("Type 'exit' or 'quit' to stop.\n")

        while True:
            user_input = Prompt.ask("[bold blue]You[/bold blue]")
            
            if user_input.lower() in ("exit", "quit"):
                break
                
            if not user_input.strip():
                continue

            with console.status("[bold yellow]AI is thinking...[/bold yellow]"):
                payload = {
                    "conversation_id": conversation_id,
                    "message": user_input,
                    "stream": False
                }
                
                try:
                    response = await client.post("/chat", json=payload)
                    
                    if response.status_code == 200:
                        data = response.json()
                        chat_data = data.get("data", {})
                        reply = chat_data.get("response", "")
                        console.print("\n[bold purple]EasyDev AI[/bold purple]")
                        console.print(Markdown(reply))
                        console.print()
                    elif response.status_code == 404:
                        console.print(f"\n[red]Error 404: Conversation '{conversation_id}' not found in the database.[/red]")
                        console.print("[yellow]Since the /conversations API isn't implemented yet, you may need to seed the database with this conversation ID manually.[/yellow]\n")
                    else:
                        console.print(f"\n[red]Error {response.status_code}:[/red] {response.text}\n")
                        
                except Exception as e:
                    console.print(f"\n[red]Request failed:[/red] {e}\n")

if __name__ == "__main__":
    asyncio.run(main())
