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


def _prompt_execute() -> str:
    """
    Prompt the user for execution choice.

    Returns:
        'y' = execute this one
        'n' = skip
        'a' = execute all remaining without asking
    """
    while True:
        choice = console.input(
            "Execute this in Resolve? [bold]([green]y[/green]es / [red]n[/red]o / [yellow]a[/yellow]ll)[/bold] "
        ).strip().lower()
        if choice in ("y", "yes"):
            return "y"
        elif choice in ("n", "no", ""):
            return "n"
        elif choice in ("a", "all"):
            return "a"
        else:
            console.print("[dim]Please enter y, n, or a.[/dim]")


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

    # State
    plan_mode = False
    auto_execute = False

    # Welcome message
    console.print()
    console.print(Panel(
        "[bold blue]DaVinci Resolve Chatbot[/bold blue]\n"
        "Ask questions about the Resolve scripting API or request automation scripts.\n\n"
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

        # Reset auto-execute per message
        auto_execute = False

        # Handle commands
        cmd = user_input.lower()
        if cmd == "/quit":
            console.print("[dim]Goodbye![/dim]")
            break
        elif cmd == "/refresh":
            session.refresh()
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
                    "your approval before generating executable code.[/dim]"
                )
            continue

        # In plan mode, prepend instruction to plan first
        if plan_mode:
            augmented_input = (
                f"{user_input}\n\n"
                "[PLAN MODE] Present a detailed step-by-step plan for this task. "
                "Do NOT generate executable code yet. Explain what each step will do, "
                "which API methods will be used, and ask for my approval before proceeding. "
                "Once I approve, generate the complete executable script."
            )
        else:
            augmented_input = user_input

        # Process message
        console.print()
        with console.status("[bold blue]Thinking...[/bold blue]"):
            try:
                result = chat.chat(augmented_input)
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
            # Split code into individual blocks for step-by-step execution
            code_blocks = _split_code_blocks(result["code"])

            for i, block in enumerate(code_blocks, 1):
                if len(code_blocks) > 1:
                    console.print(f"\n[bold]Step {i}/{len(code_blocks)}:[/bold]")

                console.print()
                console.print(Syntax(block, "python", theme="monokai", line_numbers=True))

                # Show validation result
                if result.get("validation"):
                    validation = result["validation"]
                    if validation.is_valid:
                        console.print("[green]Validation: All API calls are documented.[/green]")
                    else:
                        console.print(f"[red]Validation: {validation}[/red]")
                        console.print("[yellow]Execution blocked due to unrecognized API calls.[/yellow]")
                        break

                # Offer execution
                if session.state.is_connected:
                    if auto_execute:
                        should_execute = True
                    else:
                        choice = _prompt_execute()
                        if choice == "a":
                            auto_execute = True
                            should_execute = True
                        elif choice == "y":
                            should_execute = True
                        else:
                            should_execute = False

                    if should_execute:
                        from .executor import ResolveExecutor
                        executor = ResolveExecutor(resolve)
                        exec_result = executor.execute(block)
                        if exec_result.success:
                            console.print("[green]Execution successful.[/green]")
                            if exec_result.output:
                                console.print(f"Output:\n{exec_result.output}")
                            if exec_result.return_value is not None:
                                console.print(f"Return: {exec_result.return_value}")
                            session.update_after_action(user_input, exec_result)
                        else:
                            console.print(f"[red]Execution failed: {exec_result.error}[/red]")
                            if not auto_execute:
                                console.print("[yellow]Stopping execution.[/yellow]")
                                break
                    else:
                        console.print("[dim]Skipped.[/dim]")
                else:
                    console.print("[dim](Resolve not connected — cannot execute)[/dim]")
                    break

        console.print()


def _split_code_blocks(code: str) -> list[str]:
    """
    Split a multi-step code string into individual executable blocks.
    Splits on blank-line-separated sections that each form a logical step.
    If the code is a single cohesive script, returns it as one block.
    """
    # If code has clear step comments (# Step 1, # Step 2, etc.), split on those
    import re
    step_pattern = re.compile(r"^# (?:Step \d+|---)", re.MULTILINE)
    if step_pattern.search(code):
        parts = step_pattern.split(code)
        blocks = [p.strip() for p in parts if p.strip()]
        if len(blocks) > 1:
            return blocks

    # Otherwise return as a single block
    return [code.strip()]


if __name__ == "__main__":
    cli()
