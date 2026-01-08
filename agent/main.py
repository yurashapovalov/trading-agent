"""CLI interface for Trading Agent"""

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from data import load_csv, get_data_info, init_database
from agent.llm import TradingAgent
import config

app = typer.Typer(help="Trading Analytics Agent")
console = Console()


@app.command()
def load(
    file: str = typer.Argument(..., help="Path to CSV file"),
    symbol: str = typer.Option(..., "--symbol", "-s", help="Symbol name (e.g. CL)"),
    replace: bool = typer.Option(False, "--replace", "-r", help="Replace existing data")
):
    """Load CSV data into database."""

    console.print(f"[blue]Loading {file}...[/blue]")

    try:
        count = load_csv(file, symbol, replace=replace)
        console.print(f"[green]✓ Loaded {count:,} bars for {symbol}[/green]")

        # Show data info
        info = get_data_info()
        if not info.empty:
            table = Table(title="Loaded Data")
            table.add_column("Symbol")
            table.add_column("Bars", justify="right")
            table.add_column("Start")
            table.add_column("End")
            table.add_column("Days", justify="right")

            for _, row in info.iterrows():
                table.add_row(
                    row['symbol'],
                    f"{row['bars']:,}",
                    str(row['start_date'])[:10],
                    str(row['end_date'])[:10],
                    str(row['trading_days'])
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def info():
    """Show loaded data information."""

    try:
        data = get_data_info()
        if data.empty:
            console.print("[yellow]No data loaded yet.[/yellow]")
            return

        table = Table(title="Loaded Data")
        table.add_column("Symbol")
        table.add_column("Bars", justify="right")
        table.add_column("Start")
        table.add_column("End")
        table.add_column("Days", justify="right")

        for _, row in data.iterrows():
            table.add_row(
                row['symbol'],
                f"{row['bars']:,}",
                str(row['start_date'])[:10],
                str(row['end_date'])[:10],
                str(row['trading_days'])
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@app.command()
def chat():
    """Start interactive chat with the trading agent."""

    console.print(Panel(
        "[bold]Trading Analytics Agent[/bold]\n"
        "Ask questions about your trading data.\n"
        "Type 'quit' or 'exit' to stop.",
        title="Welcome"
    ))

    agent = TradingAgent()

    while True:
        try:
            user_input = console.input("\n[bold cyan]You:[/bold cyan] ")

            if user_input.lower() in ('quit', 'exit', 'q'):
                console.print("[yellow]Goodbye![/yellow]")
                break

            if not user_input.strip():
                continue

            if user_input.lower() == 'reset':
                agent.reset()
                console.print("[yellow]Conversation reset.[/yellow]")
                continue

            with console.status("[bold green]Thinking...", spinner="dots"):
                response = agent.chat(user_input)

            console.print(f"\n[bold green]Agent:[/bold green]")
            console.print(Markdown(response))

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Type 'quit' to exit.[/yellow]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@app.command()
def init():
    """Initialize the database."""
    init_database(config.DATABASE_PATH)
    console.print("[green]✓ Database initialized[/green]")


if __name__ == "__main__":
    app()
