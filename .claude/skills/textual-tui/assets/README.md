# Example Textual Applications

Complete, working example applications demonstrating various Textual patterns and features.

## Running the Examples

Each example is a standalone Python file. To run:

```bash
# Install dependencies
pip install textual textual-dev psutil

# Run any example
python todo_app.py
python dashboard_app.py
python data_viewer.py
python worker_demo.py

# Or with hot reload during development
textual run --dev todo_app.py
```

## Examples

### todo_app.py - Todo List Application

A fully functional todo list demonstrating:
- Input handling and form validation
- List view with custom list items
- State management with reactive attributes
- Keyboard shortcuts and bindings
- Custom styling and theming
- Toggle states and visual feedback

**Key Features:**
- Add/delete/toggle todos
- Mark items as complete
- Statistics tracking
- Keyboard shortcuts (Ctrl+N, Space, Ctrl+D, etc.)

**Patterns Demonstrated:**
- Custom widget creation (TodoItem)
- Reactive state updates
- Event handling (button press, input submit)
- Keyboard bindings
- CSS styling with pseudo-classes

### dashboard_app.py - System Monitor Dashboard

A real-time system monitoring dashboard demonstrating:
- Grid layouts for dashboard design
- Reactive data updates
- Custom composite widgets
- Data visualization with Sparkline and ProgressBar
- Real-time monitoring with intervals
- Metric cards and charts

**Key Features:**
- Live CPU and memory monitoring
- Historical CPU usage chart
- System metrics (cores, frequency, processes, uptime)
- Auto-refresh every second
- Manual refresh with 'R' key

**Patterns Demonstrated:**
- Grid-based layouts
- Custom widget composition (MetricCard, CPUChart, MemoryChart)
- Timed updates with `set_interval()`
- Reactive attributes for live updates
- Data visualization components

### data_viewer.py - JSON/CSV Data Viewer

A file browser and data viewer demonstrating:
- File system navigation with DirectoryTree
- Multiple view modes (Table, Tree, Info) with tabs
- DataTable for tabular data
- Tree widget for hierarchical data
- Modal dialogs for errors
- Search and filter functionality

**Key Features:**
- Browse and select files from file system
- Load and display JSON and CSV files
- View data as table or tree structure
- File information panel
- Search functionality
- Error handling with modal dialogs

**Patterns Demonstrated:**
- Horizontal split layout (sidebar + content)
- Tabbed content interface
- Modal screen dialogs
- File I/O and data parsing
- Dynamic data loading
- Event handling across multiple widgets

### worker_demo.py - Background Task Processing

A comprehensive worker pattern demonstration with two apps:

**FileProcessor App:**
- Single long-running worker with progress updates
- Worker cancellation
- Real-time statistics (speed, time elapsed)
- Progress bar updates from worker
- Error handling and state management

**MultiWorkerDemo App:**
- Multiple concurrent workers
- Group-based worker management
- Batch cancellation
- Independent progress tracking per worker

**Key Features:**
- Simulated file processing with 100 files
- Real-time progress updates
- Worker state change monitoring
- Cancellation support
- Statistics tracking (files/sec, elapsed time)

**Patterns Demonstrated:**
- `run_worker()` for background tasks
- Worker lifecycle management
- Thread-safe UI updates
- Progress reporting from workers
- Worker cancellation and cleanup
- Multiple concurrent workers
- Worker groups and batch operations
- Error handling in workers

## Common Patterns

All examples demonstrate these fundamental patterns:
- Proper app structure with `compose()` method
- Header and Footer usage
- Keyboard bindings
- CSS styling with Textual's CSS system
- Event handling with `on_*` methods
- Reactive state management
- Widget querying with `query_one()` and `query()`

## Learning Path

1. **Start with todo_app.py** - Learn basic input, lists, and state management
2. **Move to dashboard_app.py** - Understand layouts, custom widgets, and real-time updates
3. **Try worker_demo.py** - Master background tasks and worker patterns (IMPORTANT!)
4. **Explore data_viewer.py** - Master complex layouts, tabs, and data handling

## Extending the Examples

Feel free to modify these examples:
- Add persistence to todo_app (save/load from file)
- Add network monitoring to dashboard_app
- Add export functionality to data_viewer
- Add real file processing to worker_demo (use actual files)
- Customize the styling and themes
- Add new features and widgets

## Resources

- Textual Documentation: https://textual.textualize.io/
- Widget Gallery: See references/widgets.md
- Layout Patterns: See references/layouts.md
- Styling Guide: See references/styling.md
