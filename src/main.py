"""
CLI entrypoint for the DaVinci Resolve Chatbot.
"""

import os
import platform
import sys

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.prompt import Confirm
from dotenv import load_dotenv

load_dotenv()

console = Console()

DOCS_PATH = os.getenv("DOCS_PATH", "./docs")
VECTORSTORE_PATH = os.getenv("VECTORSTORE_PATH", "./vectorstore")


def _default_resolve_script_path() -> str:
    """Return the default Resolve scripting modules path for the current OS."""
    system = platform.system()
    if system == "Darwin":
        return "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"
    elif system == "Windows":
        return os.path.join(
            os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
            r"Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules",
        )
    return "/opt/resolve/Developer/Scripting/Modules"


def _get_resolve():
    """Try to connect to a running DaVinci Resolve instance."""
    resolve_script_path = os.getenv(
        "RESOLVE_SCRIPT_PATH",
        _default_resolve_script_path(),
    )
    if resolve_script_path not in sys.path:
        sys.path.append(resolve_script_path)

    try:
        import DaVinciResolveScript as dvr_script
        resolve = dvr_script.scriptapp("Resolve")
        return resolve
    except (ImportError, AttributeError):
        return None


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """DaVinci Resolve Chatbot — RAG-powered scripting assistant."""
    if ctx.invoked_subcommand is None:
        _start_chat()


@cli.command()
def ingest():
    """Run the ingestion pipeline to (re)build the vector store."""
    from .ingest import build_index

    console.print("[bold]Running ingestion pipeline...[/bold]")
    chunks = build_index(docs_path=DOCS_PATH, vectorstore_path=VECTORSTORE_PATH)
    console.print(f"[green]Ingestion complete. Indexed {len(chunks)} chunks.[/green]")


@cli.command()
def refresh():
    """Manually refresh the session context from Resolve."""
    from .session import Session

    resolve = _get_resolve()
    if not resolve:
        console.print("[red]Could not connect to DaVinci Resolve.[/red]")
        return

    session = Session(resolve)
    session.refresh()
    console.print(Panel(session.get_context_summary(), title="Resolve Session"))


def _start_chat():
    """Start the interactive chat loop."""
    from .session import Session
    from .tools import ToolRegistry
    from .validator import APIValidator
    from .chat import ChatOrchestrator

    # Connect to Resolve (optional)
    resolve = _get_resolve()
    session = Session(resolve)

    # Initialize retriever (if vectorstore exists)
    retriever = None
    if os.path.exists(VECTORSTORE_PATH):
        try:
            from .retriever import HybridRetriever
            retriever = HybridRetriever(vectorstore_path=VECTORSTORE_PATH)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load vector store: {e}[/yellow]")
            console.print("[yellow]Run 'ingest' command first to build the index.[/yellow]")

    # Build tool registry
    tool_registry = ToolRegistry()
    tool_registry.load_from_docs(DOCS_PATH)
    valid_methods = tool_registry.get_valid_method_names()
    validator = APIValidator(valid_methods)

    # Initialize chat orchestrator
    chat = ChatOrchestrator(
        retriever=retriever,
        session=session,
        tool_registry=tool_registry,
        validator=validator,
    )

    # Welcome message
    console.print()
    console.print(Panel(
        "[bold blue]DaVinci Resolve Chatbot[/bold blue]\n"
        "Ask questions about the Resolve scripting API or request automation scripts.\n\n"
        "Commands: /quit, /refresh, /history",
        title="Welcome",
    ))
    console.print(Panel(session.get_context_summary(), title="Session"))
    console.print()

    # Chat loop
    while True:
        try:
            user_input = console.input("[bold green]You:[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue

        # Handle commands
        if user_input.lower() == "/quit":
            console.print("[dim]Goodbye![/dim]")
            break
        elif user_input.lower() == "/refresh":
            session.refresh()
            console.print(Panel(session.get_context_summary(), title="Session Refreshed"))
            continue
        elif user_input.lower() == "/history":
            if not chat.conversation_history:
                console.print("[dim]No conversation history yet.[/dim]")
            else:
                for msg in chat.conversation_history:
                    role = msg["role"].capitalize()
                    content = msg["content"][:200]
                    if len(msg["content"]) > 200:
                        content += "..."
                    console.print(f"[bold]{role}:[/bold] {content}")
            continue

        # Process message
        console.print()
        with console.status("[bold blue]Thinking...[/bold blue]"):
            try:
                result = chat.chat(user_input)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                continue

        # Display response
        console.print("[bold blue]Assistant:[/bold blue]")
        console.print(Markdown(result["response"]))

        # Display sources
        sources = chat.get_sources(user_input)
        if sources:
            source_text = ", ".join(
                f"{s['object']}.{s['method']}" if s['method']
                else s['object'] or s['source']
                for s in sources[:3]
            )
            console.print(f"\n[dim]Sources: {source_text}[/dim]")

        # If code was generated, display and offer execution
        if result.get("code"):
            console.print()
            console.print(Syntax(result["code"], "python", theme="monokai", line_numbers=True))

            # Show validation result
            if result.get("validation"):
                validation = result["validation"]
                if validation.is_valid:
                    console.print("[green]Validation: All API calls are documented.[/green]")
                else:
                    console.print(f"[red]Validation: {validation}[/red]")
                    console.print("[yellow]Execution blocked due to unrecognized API calls.[/yellow]")
                    console.print()
                    continue

            # Offer execution
            if session.state.is_connected:
                if Confirm.ask("Execute this in Resolve?", default=False):
                    from .executor import ResolveExecutor
                    executor = ResolveExecutor(resolve)
                    exec_result = executor.execute(result["code"])
                    if exec_result.success:
                        console.print("[green]Execution successful.[/green]")
                        if exec_result.output:
                            console.print(f"Output: {exec_result.output}")
                        if exec_result.return_value is not None:
                            console.print(f"Return: {exec_result.return_value}")
                        session.update_after_action(user_input, exec_result)
                    else:
                        console.print(f"[red]Execution failed: {exec_result.error}[/red]")
            else:
                console.print("[dim](Resolve not connected — cannot execute)[/dim]")

        console.print()


if __name__ == "__main__":
    cli()
