# Textual Development Guide

This guide captures key insights and best practices learned while building the MinIO TUI with the Textual framework.

## Overview

Textual is a Python framework for building rich terminal user interfaces. It provides a reactive, component-based architecture similar to modern web frameworks but for the terminal.

## Key Concepts

### 1. App Architecture

```python
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer

class MyApp(App):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
```

**Key Insights:**
- The `compose()` method defines your UI structure
- Use `yield` to add widgets to the layout
- Apps are reactive - they respond to events and update automatically

### 2. Widgets and Layout

**Essential Widgets Used:**
- `DataTable` - For tabular data (bucket lists)
- `Tree` - For hierarchical data (object trees)
- `Input` - For text input in modals
- `Button` - For actions
- `ProgressBar` - For showing upload/download progress
- `Static` - For displaying text/content
- `Label` - For labels and titles

**Layout Containers:**
```python
from textual.containers import Horizontal, Vertical, Container

# Side-by-side layout
with Horizontal():
    yield BucketPanel()
    yield ObjectPanel()

# Stacked layout
with Vertical():
    yield Header()
    yield MainContent()
    yield Footer()

# Custom styled container
with Container(id="modal_container"):
    yield Input(placeholder="Enter name")
```

### 3. CSS Styling

Textual uses CSS-like styling with some differences:

```css
/* Size and positioning */
#buckets_panel {
    width: 30%;           /* Percentage of parent */
    height: 1fr;          /* Fractional units */
    border-right: solid $accent;
}

/* Colors use Textual variables */
.modal-title {
    color: $primary;
    text-style: bold;
    text-align: center;
}

/* Responsive design */
.modal-container {
    width: 60;            /* Fixed width in characters */
    align: center middle; /* Center alignment */
}
```

**Key CSS Insights:**
- Use `fr` units for flexible sizing (`1fr` = take available space)
- Textual color variables: `$primary`, `$surface`, `$text`, `$accent`
- `align: center middle` for centering content
- Width can be percentage (`30%`) or character count (`60`)

### 4. Modal Screens

Modal screens are separate UI components that overlay the main app:

```python
from textual.screen import ModalScreen

class UploadFileScreen(ModalScreen):
    def __init__(self, current_path=""):
        super().__init__()
        self.current_path = current_path
        
    def compose(self) -> ComposeResult:
        with Container(classes="modal-container"):
            yield Label("Upload File", classes="modal-title")
            yield Input(placeholder="File path", id="file_path")
            yield Input(placeholder="Object name", id="object_name", 
                       value=self.current_path)
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", variant="error", id="cancel")
                yield Button("Upload", variant="primary", id="upload")
```

**Modal Best Practices:**
- Use `classes="modal-container"` for consistent styling
- Initialize with data needed for the modal (like `current_path`)
- Handle both cancel and submit actions
- Use button variants: `primary`, `error`, `success`

### 5. Event Handling

Events in Textual are typed and structured:

```python
# Button events
def on_button_pressed(self, event: Button.Pressed) -> None:
    if event.button.id == "upload":
        # Handle upload
        self.dismiss({"action": "upload", "data": self.get_form_data()})
    elif event.button.id == "cancel":
        self.dismiss()

# Input events
def on_input_changed(self, event: Input.Changed) -> None:
    if event.input.id == "search":
        self.filter_objects(event.value)

# Key events
def key_q(self) -> None:
    self.exit()
    
def key_u(self) -> None:
    self.action_upload_file()
```

**Event Insights:**
- Use typed event handlers (`Button.Pressed`, `Input.Changed`)
- `key_x` methods handle individual key presses
- `action_x` methods are reusable actions that can be triggered by keys or buttons
- `dismiss(data)` closes modals and passes data back to the parent

### 6. Actions and Keybindings

Define actions that can be triggered by multiple methods:

```python
class MinioTUI(App):
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("u", "upload_file", "Upload"),
        ("d", "toggle_dark", "Dark mode"),
        ("tab", "focus_next", "Next panel"),
    ]
    
    def action_upload_file(self):
        # Implementation here
        pass
        
    def action_toggle_dark(self):
        self.dark = not self.dark
```

**Keybinding Best Practices:**
- Use consistent, intuitive key mappings
- Group related actions (file operations, navigation, etc.)
- Provide both key shortcuts and button/menu access
- Display current keybindings in status bar or footer

### 7. Working with Trees

Trees are powerful for hierarchical data like file systems:

```python
def update_object_tree(self, objects):
    tree = self.query_one("#objects_tree")
    tree.clear()
    
    # Build tree structure
    dirs = {}
    
    for obj in objects:
        path_parts = obj['key'].split('/')
        current_level = dirs
        
        # Build nested directory structure
        for i, part in enumerate(path_parts[:-1]):
            if part not in current_level:
                current_level[part] = {}
            current_level = current_level[part]
        
        # Add file to final directory
        filename = path_parts[-1]
        if filename:  # Not a directory marker
            current_level[filename] = obj
    
    # Add to tree with icons
    def add_nodes(parent_node, level_dict, prefix=""):
        for name, content in sorted(level_dict.items()):
            if isinstance(content, dict):
                # Directory
                icon = get_file_icon(name + "/")
                node = parent_node.add(f"{icon} {name}", expand=True)
                add_nodes(node, content, prefix + name + "/")
            else:
                # File
                icon = get_file_icon(name)
                parent_node.add_leaf(f"{icon} {name}", data=content['key'])
    
    add_nodes(tree.root, dirs)
```

**Tree Insights:**
- Use `add_leaf()` for files, `add()` for directories
- Store data in `data` attribute for easy retrieval
- Icons make the interface much more intuitive
- Recursive functions work well for tree building
- `expand=True` auto-expands directory nodes

### 8. Threading and Workers

For long-running operations, use threading to keep UI responsive:

```python
import threading
from textual.worker import work_thread

def _start_upload_with_progress(self, file_path, object_name, progress_screen):
    def progress_callback(bytes_transferred):
        if not progress_screen.cancelled:
            self.call_from_thread(progress_screen.update_progress, bytes_transferred)
    
    def upload_worker():
        try:
            self.minio_client.upload_file(
                self.current_bucket, 
                object_name, 
                file_path, 
                progress_callback=progress_callback,
                cancel_event=progress_screen.cancel_event
            )
            if not progress_screen.cancelled:
                self.call_from_thread(progress_screen.dismiss, None)
        except Exception as e:
            self.call_from_thread(progress_screen.dismiss, {"error": str(e)})
    
    upload_thread = threading.Thread(target=upload_worker, daemon=True)
    upload_thread.start()
```

**Threading Best Practices:**
- Use `self.call_from_thread()` to update UI from worker threads
- Use `daemon=True` so threads don't prevent app shutdown
- Implement cancellation with `threading.Event()`
- Handle exceptions in worker threads and report back to UI
- Use progress callbacks for long operations

### 9. CSS Responsive Design

```css
/* Container sizes */
.modal-container {
    width: 50;     /* Medium modal */
    height: auto;
}

.preview-modal-container {
    width: 90%;    /* Large modal - percentage of screen */
    height: 80%;
}

#progress_container {
    width: 60;     /* Fixed width for progress */
    height: 15;
}

/* Responsive panels */
#buckets_panel {
    width: 30%;    /* Takes 30% of available width */
}

#objects_panel {
    width: 70%;    /* Takes remaining 70% */
}
```

### 10. Performance Tips

**Efficient Updates:**
```python
# Use run_worker for expensive operations
self.run_worker(self.load_buckets_and_counts, thread=True)

# Batch updates when possible
def update_status_efficiently(self):
    # Update multiple elements at once
    self.query_one("#status").update("Ready")
    self.query_one("#bucket_count").update(f"{len(buckets)} buckets")
```

**Memory Management:**
```python
# Clear large widgets when switching contexts
def clear_objects_tree(self):
    tree = self.query_one("#objects_tree")
    tree.clear()  # Frees memory from old tree data
```

## Common Patterns

### 1. Modal with Form Validation

```python
class CreateBucketScreen(ModalScreen):
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create":
            bucket_name = self.query_one("#bucket_name").value.strip()
            if not bucket_name:
                self.query_one("#error").update("Bucket name is required")
                return
            if not self.validate_bucket_name(bucket_name):
                self.query_one("#error").update("Invalid bucket name")
                return
            self.dismiss({"name": bucket_name})
```

### 2. Context-Sensitive Actions

```python
def get_current_context(self):
    """Return current focus context for keybindings."""
    if self.focused and self.focused.id == "buckets_table":
        return "bucket"
    elif self.focused and self.focused.id == "objects_tree":
        return "object"
    return "app"

def compose(self) -> ComposeResult:
    # Update footer based on context
    context = self.get_current_context()
    if context == "bucket":
        yield Footer("c: Create bucket | x: Delete | Tab: Switch panel")
    elif context == "object":
        yield Footer("u: Upload | l: Download | x: Delete | Tab: Switch panel")
```

### 3. Smart Path Handling

```python
def get_current_path(self):
    """Get current directory path for smart prepopulation."""
    if self.focused and self.focused.id == "objects_tree":
        node = self.query_one("#objects_tree").cursor_node
        if node and node.data:
            path = node.data
            if path.endswith('/'):
                return path
            # Return parent directory
            parts = path.split('/')
            if len(parts) > 1:
                return '/'.join(parts[:-1]) + '/'
    return ""
```

## Debugging Tips

1. **Use `log()` for debugging:** `self.log(f"Debug: {variable}")`
2. **CSS Inspector:** Run with `--dev` flag for live CSS editing
3. **Widget IDs:** Always use meaningful IDs for widgets you need to query
4. **Event Logging:** Log events to understand the flow
5. **State Management:** Keep state in the app, not in widgets

## Testing Strategies

```python
# Test widget initialization
def test_app_initialization(self):
    app = MinioTUI()
    assert app.title == "MinIO TUI"

# Test modal behavior
async def test_modal_submit():
    app = MinioTUI()
    async with app.run_test() as pilot:
        app.push_screen(CreateBucketScreen())
        await pilot.click("#create")
        # Assert expected behavior
```

## Common Pitfalls

1. **Not using `call_from_thread()`** - UI updates from worker threads will fail
2. **Forgetting CSS imports** - Widget styling won't work
3. **Heavy operations in main thread** - UI will freeze
4. **Not handling widget state** - Widgets maintain their own state
5. **Circular imports** - Structure your modules carefully
6. **Memory leaks** - Clear large widgets when done
7. **Event handling order** - Events bubble up, handle at the right level

## Architecture Recommendations

```
app.py              # Main app, event handling, business logic
minio_client.py     # External API wrapper
simple_config.py    # Configuration management
app.css            # All styling
run.py             # Entry point
tests/             # Comprehensive test suite
```

This architecture separates concerns cleanly and makes the codebase maintainable and testable.