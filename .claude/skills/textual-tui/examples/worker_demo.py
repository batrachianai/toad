"""
File Processor - Textual TUI Worker Example

Demonstrates:
- Worker patterns for background tasks
- Progress updates from workers
- Worker cancellation
- Error handling in workers
- Multiple concurrent workers
- Thread-safe UI updates
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Button, ProgressBar, Log, Static, Label
from textual.worker import Worker, WorkerState
from pathlib import Path
import asyncio
import time
import hashlib


class FileProcessor(App):
    """File processing app demonstrating worker patterns."""
    
    CSS = """
    Screen {
        background: $background;
    }
    
    Header {
        background: $primary;
    }
    
    #main {
        padding: 1 2;
        height: 1fr;
    }
    
    #controls {
        height: auto;
        margin-bottom: 1;
    }
    
    Button {
        margin: 0 1;
    }
    
    #progress-container {
        border: solid $primary;
        padding: 1;
        margin-bottom: 1;
        height: auto;
        background: $surface;
    }
    
    #progress-label {
        margin-bottom: 1;
        text-style: bold;
        color: $accent;
    }
    
    ProgressBar {
        margin-bottom: 1;
    }
    
    #stats {
        height: 5;
        border: solid $accent;
        padding: 1;
        margin-bottom: 1;
        background: $panel;
    }
    
    .stat-line {
        margin: 0;
    }
    
    #log {
        border: solid $primary;
        height: 1fr;
        background: $surface;
    }
    """
    
    BINDINGS = [
        ("s", "start", "Start"),
        ("c", "cancel", "Cancel"),
        ("r", "reset", "Reset"),
        ("q", "quit", "Quit"),
    ]
    
    def __init__(self) -> None:
        super().__init__()
        self.main_worker: Worker | None = None
        self.processed_count = 0
        self.total_files = 0
        self.start_time = 0.0
    
    def compose(self) -> ComposeResult:
        """Compose the UI."""
        yield Header(show_clock=True)
        
        with Container(id="main"):
            with Horizontal(id="controls"):
                yield Button("Start Processing", variant="success", id="start")
                yield Button("Cancel", variant="error", id="cancel", disabled=True)
                yield Button("Reset", id="reset")
            
            with Container(id="progress-container"):
                yield Label("Progress", id="progress-label")
                yield ProgressBar(total=100, show_percentage=True, id="progress")
            
            with Container(id="stats"):
                yield Static("Status: Idle", classes="stat-line", id="status")
                yield Static("Files Processed: 0 / 0", classes="stat-line", id="files")
                yield Static("Time Elapsed: 0s", classes="stat-line", id="time")
                yield Static("Speed: 0 files/sec", classes="stat-line", id="speed")
            
            yield Log(id="log", auto_scroll=True)
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize on mount."""
        log = self.query_one("#log", Log)
        log.write_line("[bold cyan]File Processor Started[/]")
        log.write_line("Click 'Start Processing' or press 'S' to begin")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "start":
            self.action_start()
        elif event.button.id == "cancel":
            self.action_cancel()
        elif event.button.id == "reset":
            self.action_reset()
    
    def action_start(self) -> None:
        """Start file processing worker."""
        if self.main_worker and not self.main_worker.is_finished:
            self.log_message("[yellow]Processing already in progress[/]")
            return
        
        # Disable start button, enable cancel
        self.query_one("#start", Button).disabled = True
        self.query_one("#cancel", Button).disabled = False
        
        # Reset counters
        self.processed_count = 0
        self.total_files = 100  # Simulated file count
        self.start_time = time.time()
        
        # Start worker
        self.log_message("[bold green]Starting file processing...[/]")
        self.main_worker = self.run_worker(
            self.process_files(),
            name="file_processor",
            group="processing"
        )
    
    def action_cancel(self) -> None:
        """Cancel the running worker."""
        if self.main_worker and not self.main_worker.is_finished:
            self.main_worker.cancel()
            self.log_message("[bold red]Cancelling worker...[/]")
    
    def action_reset(self) -> None:
        """Reset the UI."""
        if self.main_worker and not self.main_worker.is_finished:
            self.log_message("[yellow]Cannot reset while processing[/]")
            return
        
        self.processed_count = 0
        self.total_files = 0
        
        progress = self.query_one("#progress", ProgressBar)
        progress.update(progress=0)
        
        self.update_stats()
        self.log_message("[cyan]Reset complete[/]")
    
    async def process_files(self) -> None:
        """
        Worker task: Process files in background.
        
        Demonstrates:
        - Long-running async operations
        - Progress updates via call_from_thread
        - Cancellation checking
        - Error handling
        """
        try:
            for i in range(self.total_files):
                # Check if cancelled
                if self.main_worker and self.main_worker.is_cancelled:
                    self.log_message("[red]Processing cancelled![/]")
                    self.finalize_processing(cancelled=True)
                    return
                
                # Simulate file processing (async I/O)
                await asyncio.sleep(0.05)
                
                # Simulate some work
                filename = f"file_{i:04d}.txt"
                hash_val = hashlib.md5(filename.encode()).hexdigest()[:8]
                
                # Update progress (thread-safe)
                self.processed_count = i + 1
                progress = (self.processed_count / self.total_files) * 100
                
                # Update UI from worker
                self.update_progress(progress, filename, hash_val)
                
                # Log every 10th file
                if (i + 1) % 10 == 0:
                    self.log_message(
                        f"[green]Processed {self.processed_count}/{self.total_files} files[/]"
                    )
            
            # Completed successfully
            self.log_message("[bold green]✓ All files processed successfully![/]")
            self.finalize_processing(cancelled=False)
            
        except Exception as e:
            self.log_message(f"[bold red]Error: {e}[/]")
            self.finalize_processing(cancelled=False)
            raise
    
    def update_progress(self, progress: float, filename: str, hash_val: str) -> None:
        """Update progress bar and stats (called from worker)."""
        progress_bar = self.query_one("#progress", ProgressBar)
        progress_bar.update(progress=progress)
        
        # Update stats
        self.update_stats()
        
        # Update status
        status = self.query_one("#status", Static)
        status.update(f"Status: Processing {filename} [{hash_val}]")
    
    def update_stats(self) -> None:
        """Update statistics display."""
        files_stat = self.query_one("#files", Static)
        files_stat.update(f"Files Processed: {self.processed_count} / {self.total_files}")
        
        elapsed = time.time() - self.start_time if self.start_time > 0 else 0
        time_stat = self.query_one("#time", Static)
        time_stat.update(f"Time Elapsed: {elapsed:.1f}s")
        
        speed = self.processed_count / elapsed if elapsed > 0 else 0
        speed_stat = self.query_one("#speed", Static)
        speed_stat.update(f"Speed: {speed:.1f} files/sec")
    
    def finalize_processing(self, cancelled: bool) -> None:
        """Finalize after processing completes or is cancelled."""
        # Re-enable buttons
        self.query_one("#start", Button).disabled = False
        self.query_one("#cancel", Button).disabled = True
        
        # Update status
        status = self.query_one("#status", Static)
        if cancelled:
            status.update("Status: Cancelled")
        else:
            status.update("Status: Complete")
    
    def log_message(self, message: str) -> None:
        """Thread-safe log message."""
        log = self.query_one("#log", Log)
        log.write_line(message)
    
    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker state changes."""
        if event.worker.name != "file_processor":
            return
        
        if event.state == WorkerState.PENDING:
            self.log_message("[cyan]Worker: Pending...[/]")
        elif event.state == WorkerState.RUNNING:
            self.log_message("[cyan]Worker: Running[/]")
        elif event.state == WorkerState.CANCELLED:
            self.log_message("[red]Worker: Cancelled[/]")
        elif event.state == WorkerState.ERROR:
            self.log_message(f"[bold red]Worker: Error - {event.worker.error}[/]")
        elif event.state == WorkerState.SUCCESS:
            self.log_message("[green]Worker: Completed successfully[/]")


class MultiWorkerDemo(App):
    """Demonstrates running multiple concurrent workers."""
    
    CSS = """
    Screen {
        background: $background;
    }
    
    #main {
        padding: 1 2;
    }
    
    #controls {
        height: auto;
        margin-bottom: 1;
    }
    
    Button {
        margin: 0 1;
    }
    
    .worker-card {
        border: solid $primary;
        padding: 1;
        margin-bottom: 1;
        background: $surface;
    }
    
    .worker-card .title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    
    #log {
        border: solid $primary;
        height: 20;
    }
    """
    
    BINDINGS = [
        ("s", "start_all", "Start All"),
        ("c", "cancel_all", "Cancel All"),
        ("q", "quit", "Quit"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        with Container(id="main"):
            with Horizontal(id="controls"):
                yield Button("Start All Workers", variant="success", id="start")
                yield Button("Cancel All", variant="error", id="cancel")
            
            with Container(classes="worker-card"):
                yield Label("Worker 1: Data Fetch", classes="title")
                yield ProgressBar(total=100, id="worker1")
            
            with Container(classes="worker-card"):
                yield Label("Worker 2: Data Process", classes="title")
                yield ProgressBar(total=100, id="worker2")
            
            with Container(classes="worker-card"):
                yield Label("Worker 3: Data Export", classes="title")
                yield ProgressBar(total=100, id="worker3")
            
            yield Log(id="log", auto_scroll=True)
        
        yield Footer()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            self.action_start_all()
        elif event.button.id == "cancel":
            self.action_cancel_all()
    
    def action_start_all(self) -> None:
        """Start all workers concurrently."""
        self.run_worker(self.worker_task(1, 3.0), name="worker1", group="tasks")
        self.run_worker(self.worker_task(2, 5.0), name="worker2", group="tasks")
        self.run_worker(self.worker_task(3, 4.0), name="worker3", group="tasks")
        
        log = self.query_one("#log", Log)
        log.write_line("[bold cyan]Started all workers concurrently[/]")
    
    def action_cancel_all(self) -> None:
        """Cancel all workers in the group."""
        for worker in self.workers:
            if worker.group == "tasks":
                worker.cancel()
        
        log = self.query_one("#log", Log)
        log.write_line("[bold red]Cancelled all workers[/]")
    
    async def worker_task(self, worker_num: int, duration: float) -> None:
        """Simulated worker task."""
        log = self.query_one("#log", Log)
        log.write_line(f"[cyan]Worker {worker_num} started[/]")
        
        progress_bar = self.query_one(f"#worker{worker_num}", ProgressBar)
        steps = 100
        
        for i in range(steps):
            await asyncio.sleep(duration / steps)
            progress_bar.update(progress=i + 1)
        
        log.write_line(f"[green]Worker {worker_num} completed![/]")


if __name__ == "__main__":
    # Run the single worker demo
    app = FileProcessor()
    app.run()
    
    # Or run the multi-worker demo
    # app = MultiWorkerDemo()
    # app.run()
