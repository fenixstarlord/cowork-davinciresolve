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
    from .executor import ResolveExecutor
    from .chat import ChatOrchestrator, StepInfo

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

    # Initialize executor (if Resolve is connected)
    executor = ResolveExecutor(resolve) if resolve else None

    # Step approval state — mutable container so the closure can modify it
    approval_state = {"auto_execute": False}

    def on_step(step: StepInfo) -> bool:
        """Called before each tool execution. Returns True to execute."""
        desc = step.description or step.tool_name
        console.print(f"\n[bold yellow]> {desc}[/bold yellow]")
        console.print(Syntax(step.code, "python", theme="monokai"))

        if approval_state["auto_execute"]:
            return True

        choice = _prompt_execute()
        if choice == "a":
            approval_state["auto_execute"] = True
            return True
        elif choice == "y":
            return True
        else:
            return False

    def on_text(text: str):
        """Called when the LLM produces text between tool calls."""
        console.print(Markdown(text))

    # Initialize chat orchestrator
    chat = ChatOrchestrator(
        retriever=retriever,
        session=session,
        tool_registry=tool_registry,
        validator=validator,
        executor=executor,
        on_step=on_step,
    )

    # State
    plan_mode = False

    # Welcome message
    console.print()
    console.print(Panel(
        "[bold blue]DaVinci Resolve Assistant[/bold blue]\n"
        "I execute Resolve API calls step by step. Ask me to do anything.\n\n"
        "Commands: [bold]/quit[/bold], [bold]/refresh[/bold], [bold]/history[/bold], [bold]/plan[/bold]",
        title="Welcome",
    ))
    console.print(Panel(session.get_context_summary(), title="Session"))
    console.print()

    # Chat loop
    while True:
        try:
            mode_tag = " [bold magenta](plan)[/bold magenta]" if plan_mode else ""
            user_input = console.input(f"[bold green]You:{mode_tag}[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue

        # Reset auto-execute for each new message
        approval_state["auto_execute"] = False

        # Handle commands
        cmd = user_input.lower()
        if cmd == "/quit":
            console.print("[dim]Goodbye![/dim]")
            break
        elif cmd == "/refresh":
            session.refresh()
            if executor:
                executor.refresh_namespace()
            console.print(Panel(session.get_context_summary(), title="Session Refreshed"))
            continue
        elif cmd == "/history":
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
        elif cmd == "/plan":
            plan_mode = not plan_mode
            state = "[bold magenta]ON[/bold magenta]" if plan_mode else "[dim]OFF[/dim]"
            console.print(f"Plan mode: {state}")
            if plan_mode:
                console.print(
                    "[dim]The assistant will present a detailed plan and wait for "
                    "your approval before executing any API calls.[/dim]"
                )
            continue

        # In plan mode, instruct the LLM to plan first
        if plan_mode:
            augmented_input = (
                f"{user_input}\n\n"
                "[PLAN MODE] First, present a detailed step-by-step plan of what you "
                "will do. List each API call you intend to make and explain why. "
                "Do NOT make any tool calls yet. After I approve the plan, I will "
                "ask you to execute it."
            )
        else:
            augmented_input = user_input

        # Process message
        console.print()
        try:
            result = chat.chat(augmented_input, on_text=on_text)
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted.[/yellow]")
            continue
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            continue

        # Show step results summary
        steps = result.get("steps", [])
        if steps:
            console.print()
            succeeded = sum(1 for s in steps if s.result and s.result.success)
            skipped = sum(1 for s in steps if s.skipped)
            failed = sum(1 for s in steps if s.result and not s.result.success)
            parts = []
            if succeeded:
                parts.append(f"[green]{succeeded} succeeded[/green]")
            if failed:
                parts.append(f"[red]{failed} failed[/red]")
            if skipped:
                parts.append(f"[dim]{skipped} skipped[/dim]")
            console.print(f"Steps: {', '.join(parts)}")

        # Display sources
        sources = chat.get_sources(user_input)
        if sources:
            source_text = ", ".join(
                f"{s['object']}.{s['method']}" if s['method']
                else s['object'] or s['source']
                for s in sources[:3]
            )
            console.print(f"[dim]Sources: {source_text}[/dim]")

        console.print()


def _prompt_execute() -> str:
    """
    Prompt the user for execution choice.
    Returns: 'y', 'n', or 'a' (execute all remaining).
    """
    while True:
        choice = console.input(
            "[bold]Execute? ([green]y[/green]es / [red]n[/red]o / [yellow]a[/yellow]ll)[/bold] "
        ).strip().lower()
        if choice in ("y", "yes"):
            return "y"
        elif choice in ("n", "no", ""):
            return "n"
        elif choice in ("a", "all"):
            return "a"
        else:
            console.print("[dim]Please enter y, n, or a.[/dim]")


if __name__ == "__main__":
    cli()
