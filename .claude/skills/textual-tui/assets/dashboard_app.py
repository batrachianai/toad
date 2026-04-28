"""
System Monitor Dashboard - Textual TUI Example

Demonstrates:
- Grid layouts for dashboard design
- Reactive data updates
- Custom widgets
- Data visualization with Sparkline
- Real-time monitoring
- Worker threads for background tasks
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Grid
from textual.widgets import Header, Footer, Static, Sparkline, ProgressBar
from textual.reactive import reactive
from textual.worker import Worker
import psutil
import time
from collections import deque


class MetricCard(Static):
    """A card displaying a metric with a label and value."""
    
    DEFAULT_CSS = """
    MetricCard {
        border: solid $primary;
        padding: 1;
        height: 7;
        background: $surface;
    }
    
    MetricCard .label {
        text-style: bold;
        color: $accent;
    }
    
    MetricCard .value {
        text-align: center;
        text-style: bold;
        color: $success;
        margin-top: 1;
    }
    """
    
    value = reactive("")
    label = reactive("")
    
    def __init__(self, label: str, initial_value: str = "0") -> None:
        super().__init__()
        self.label = label
        self.value = initial_value
    
    def compose(self) -> ComposeResult:
        yield Static(self.label, classes="label")
        yield Static(self.value, classes="value", id=f"value-{id(self)}")
    
    def watch_value(self, new_value: str) -> None:
        """Update the value display when it changes."""
        value_widget = self.query_one(f"#value-{id(self)}", Static)
        value_widget.update(new_value)


class CPUChart(Static):
    """A widget showing CPU usage over time."""
    
    DEFAULT_CSS = """
    CPUChart {
        border: solid $primary;
        padding: 1;
        height: 12;
        background: $surface;
    }
    
    CPUChart .title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    """
    
    def __init__(self) -> None:
        super().__init__()
        self.history = deque([0] * 50, maxlen=50)
    
    def compose(self) -> ComposeResult:
        yield Static("CPU Usage History", classes="title")
        yield Sparkline(list(self.history), id="cpu-sparkline")
        yield ProgressBar(total=100, show_percentage=True, id="cpu-progress")
    
    def update_cpu(self, value: float) -> None:
        """Update CPU usage display."""
        self.history.append(value)
        
        sparkline = self.query_one("#cpu-sparkline", Sparkline)
        sparkline.data = list(self.history)
        
        progress = self.query_one("#cpu-progress", ProgressBar)
        progress.update(progress=value)


class MemoryChart(Static):
    """A widget showing memory usage."""
    
    DEFAULT_CSS = """
    MemoryChart {
        border: solid $primary;
        padding: 1;
        height: 12;
        background: $surface;
    }
    
    MemoryChart .title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    
    MemoryChart .detail {
        margin-top: 1;
        color: $text-muted;
    }
    """
    
    def compose(self) -> ComposeResult:
        yield Static("Memory Usage", classes="title")
        yield ProgressBar(total=100, show_percentage=True, id="mem-progress")
        yield Static("", classes="detail", id="mem-detail")
    
    def update_memory(self, percent: float, used: float, total: float) -> None:
        """Update memory usage display."""
        progress = self.query_one("#mem-progress", ProgressBar)
        progress.update(progress=percent)
        
        detail = self.query_one("#mem-detail", Static)
        detail.update(f"Used: {used:.1f} GB / Total: {total:.1f} GB")


class SystemMonitor(App):
    """A system monitoring dashboard."""
    
    CSS = """
    Screen {
        background: $background;
    }
    
    Header {
        background: $primary;
    }
    
    #dashboard {
        padding: 1 2;
        height: 1fr;
    }
    
    #metrics-grid {
        grid-size: 4;
        grid-gutter: 1 2;
        height: auto;
        margin-bottom: 1;
    }
    
    #charts-grid {
        grid-size: 2;
        grid-gutter: 1 2;
        height: 1fr;
    }
    
    #status {
        dock: bottom;
        height: 1;
        background: $panel;
        padding: 0 2;
        color: $text-muted;
    }
    """
    
    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("q", "quit", "Quit"),
    ]
    
    update_count = reactive(0)
    
    def compose(self) -> ComposeResult:
        """Compose the dashboard UI."""
        yield Header(show_clock=True)
        
        with Container(id="dashboard"):
            with Grid(id="metrics-grid"):
                yield MetricCard("CPU Cores", f"{psutil.cpu_count()}")
                yield MetricCard("CPU Freq", "0 MHz")
                yield MetricCard("Processes", "0")
                yield MetricCard("Uptime", "0h 0m")
            
            with Grid(id="charts-grid"):
                yield CPUChart()
                yield MemoryChart()
        
        yield Static("", id="status")
        yield Footer()
    
    def on_mount(self) -> None:
        """Start monitoring when app starts."""
        self.update_system_info()
        self.set_interval(1.0, self.update_system_info)
    
    def update_system_info(self) -> None:
        """Update all system information."""
        self.update_count += 1
        
        # Update metrics
        cpu_freq = psutil.cpu_freq()
        if cpu_freq:
            freq_card = self.query("MetricCard")[1]
            freq_card.value = f"{cpu_freq.current:.0f} MHz"
        
        process_count = len(psutil.pids())
        proc_card = self.query("MetricCard")[2]
        proc_card.value = f"{process_count}"
        
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        uptime_card = self.query("MetricCard")[3]
        uptime_card.value = f"{hours}h {minutes}m"
        
        # Update CPU chart
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_chart = self.query_one(CPUChart)
        cpu_chart.update_cpu(cpu_percent)
        
        # Update memory chart
        mem = psutil.virtual_memory()
        mem_chart = self.query_one(MemoryChart)
        mem_chart.update_memory(
            mem.percent,
            mem.used / (1024**3),
            mem.total / (1024**3)
        )
        
        # Update status
        status = self.query_one("#status", Static)
        status.update(f"Last updated: {time.strftime('%H:%M:%S')} | Updates: {self.update_count}")
    
    def action_refresh(self) -> None:
        """Manually refresh the data."""
        self.update_system_info()
        self.notify("Data refreshed!", severity="information")


if __name__ == "__main__":
    app = SystemMonitor()
    app.run()
