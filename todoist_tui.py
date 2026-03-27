from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.message import Message
from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Label, LoadingIndicator, Static, Tree
from textual.worker import get_current_worker

load_dotenv()

TOKEN = os.getenv("TODOIST_TOKEN")
BASE_URL = "https://api.todoist.com/api/v1"
REPO_PATH = Path(__file__).resolve().parent
LAST_UPDATE_FILE = REPO_PATH / ".last_update"

try:
    TTY = int(os.getenv("TTY", "3600"))
except ValueError:
    TTY = 3600


# ── Update Check ──────────────────────────────────────────────────────────────

def _needs_update() -> bool:
    if not LAST_UPDATE_FILE.exists():
        return True
    try:
        last = float(LAST_UPDATE_FILE.read_text().strip())
        return (time.time() - last) >= TTY
    except ValueError:
        return True


def _write_last_update() -> None:
    LAST_UPDATE_FILE.write_text(str(time.time()))


# ── API ──────────────────────────────────────────────────────────────────────

def _headers() -> dict:
    return {"Authorization": f"Bearer {TOKEN}"}


def _get(path: str, params: dict | None = None) -> list:
    params = dict(params) if params else {}
    results: list = []
    while True:
        r = requests.get(f"{BASE_URL}/{path}", headers=_headers(), params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and "results" in data:
            results.extend(data["results"])
            cursor = data.get("next_cursor")
            if not cursor:
                break
            params["cursor"] = cursor
        else:
            return data if isinstance(data, list) else results
    return results


def _post(path: str, json: dict | None = None) -> dict | None:
    r = requests.post(f"{BASE_URL}/{path}", headers=_headers(), json=json, timeout=10)
    r.raise_for_status()
    return r.json() if r.content else None


def api_get_projects() -> list:
    return _get("projects")


def api_get_sections(project_id: str) -> list:
    return _get("sections", params={"project_id": project_id})


def api_get_tasks(project_id: str) -> list:
    return _get("tasks", params={"project_id": project_id})


def api_add_task(
    content: str,
    project_id: str,
    section_id: str | None = None,
    description: str | None = None,
) -> dict:
    data: dict = {"content": content, "project_id": project_id}
    if section_id:
        data["section_id"] = section_id
    if description:
        data["description"] = description
    return _post("tasks", json=data)


def api_close_task(task_id: str) -> None:
    _post(f"tasks/{task_id}/close")


def api_get_task(task_id: str) -> dict:
    r = requests.get(f"{BASE_URL}/tasks/{task_id}", headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json()


def api_update_task(task_id: str, content: str, description: str | None) -> dict:
    data: dict = {"content": content, "description": description or ""}
    r = requests.post(f"{BASE_URL}/tasks/{task_id}", headers=_headers(), json=data, timeout=10)
    r.raise_for_status()
    return r.json()


def api_reopen_task(task_id: str) -> None:
    _post(f"tasks/{task_id}/reopen")


def api_delete_task(task_id: str) -> None:
    r = requests.delete(f"{BASE_URL}/tasks/{task_id}", headers=_headers(), timeout=10)
    r.raise_for_status()


def api_move_task(task_id: str, section_id: str | None, project_id: str | None = None) -> dict:
    """Move a task using the dedicated /move endpoint (REST API v1)."""
    data: dict = {}
    if section_id is not None:
        data["section_id"] = section_id
    elif project_id is not None:
        data["project_id"] = project_id
    r = requests.post(
        f"{BASE_URL}/tasks/{task_id}/move", headers=_headers(), json=data, timeout=10
    )
    r.raise_for_status()
    return r.json() if r.content else {}


# ── Label helpers ─────────────────────────────────────────────────────────────

def _clean_task_label(content: str) -> Text:
    """Base label for a task node (no line number, no state styling)."""
    return Text(f"    ○ {content}")


def _build_displayed_label(base: Text | str, line_num: int,
                            pending: bool = False, moving: bool = False) -> Text:
    num = Text(f"{line_num:>3}│", style="dim cyan")
    content = base.copy() if isinstance(base, Text) else Text(str(base))
    if moving:
        content.stylize("bold yellow")
    elif pending:
        content.stylize("dim")
    return Text.assemble(num, content)


# ── Custom Tree ───────────────────────────────────────────────────────────────

class TaskTree(Tree):
    """Posts TaskActivated on Enter for task nodes; app decides what to do."""

    class TaskActivated(Message):
        def __init__(self, node, node_data: dict) -> None:
            super().__init__()
            self.node = node
            self.node_data = node_data

    def on_key(self, event) -> None:
        if event.key == "enter":
            node = self.cursor_node
            if node and node.data and node.data.get("type") == "task":
                event.prevent_default()
                self.post_message(TaskTree.TaskActivated(node, node.data))


# ── Update Modal ──────────────────────────────────────────────────────────────

class UpdateModal(ModalScreen):
    BINDINGS = [
        Binding("escape", "cancel_update", "Cancel", show=True),
        Binding("q", "quit_app", "Quit", show=True),
    ]

    DEFAULT_CSS = """
    UpdateModal { align: center middle; }
    #update-box {
        width: 56; height: auto; background: $surface;
        border: thick $warning; padding: 1 2;
    }
    #update-title { text-align: center; text-style: bold; margin-bottom: 1; color: $warning; }
    LoadingIndicator { height: 3; color: $warning; }
    #update-status { text-align: center; color: $text-muted; height: 1; }
    #update-hint { text-align: center; color: $text-muted; margin-top: 1; }
    """

    def compose(self) -> ComposeResult:
        yield Container(
            Label("🔄  Updating repository...", id="update-title"),
            LoadingIndicator(),
            Label("", id="update-status"),
            Label("[Esc] Cancel    [q] Quit", id="update-hint"),
            id="update-box",
        )

    def on_mount(self) -> None:
        self._run_git_pull()

    @work(thread=True, exclusive=True)
    def _run_git_pull(self) -> None:
        worker = get_current_worker()
        try:
            result = subprocess.run(
                ["git", "-C", str(REPO_PATH), "pull"],
                capture_output=True, text=True, timeout=30,
            )
            if worker.is_cancelled:
                return
            if result.returncode == 0:
                msg = result.stdout.strip() or "Already up to date"
                self.app.call_from_thread(self._on_done, True, msg)
            else:
                err = result.stderr.strip() or "Unknown error"
                self.app.call_from_thread(self._on_done, False, err)
        except subprocess.TimeoutExpired:
            if not worker.is_cancelled:
                self.app.call_from_thread(self._on_done, False, "Timeout (30s)")
        except Exception as e:
            if not worker.is_cancelled:
                self.app.call_from_thread(self._on_done, False, str(e))

    def _on_done(self, success: bool, message: str) -> None:
        _write_last_update()
        self.query_one("#update-status", Label).update(
            f"✓  {message}" if success else f"✗  {message}"
        )
        self.query_one("#update-hint", Label).update("[Esc] Continue    [q] Quit")
        self.query_one(LoadingIndicator).display = False
        _result = success

        def _do_dismiss() -> None:
            self.dismiss(_result)

        self.set_timer(1.5, _do_dismiss)

    def action_cancel_update(self) -> None:
        self.workers.cancel_all()
        _write_last_update()

        def _do_dismiss() -> None:
            self.dismiss(None)

        self.call_after_refresh(_do_dismiss)

    def action_quit_app(self) -> None:
        self.workers.cancel_all()
        self.app.exit()


# ── Add Task Modal ────────────────────────────────────────────────────────────

class AddTaskModal(ModalScreen):
    DEFAULT_CSS = """
    AddTaskModal { align: center middle; }
    #dialog {
        width: 68; height: auto; background: $surface;
        border: thick $primary; padding: 1 2;
    }
    #dialog-title { text-style: bold; margin-bottom: 1; }
    .field-label { color: $text-muted; margin-top: 1; }
    #dialog-hint { color: $text-muted; margin-top: 1; text-align: right; }
    #dialog Input { width: 100%; }
    """

    def __init__(self, project_id: str, section_id: str | None, location: str) -> None:
        super().__init__()
        self.project_id = project_id
        self.section_id = section_id
        self.location = location

    def compose(self) -> ComposeResult:
        hint = f" → {self.location}" if self.location else ""
        yield Container(
            Label(f"Add Task{hint}", id="dialog-title"),
            Label("Task Name *", classes="field-label"),
            Input(placeholder="Enter task name...", id="input-name"),
            Label("Description (optional)", classes="field-label"),
            Input(placeholder="Enter description...", id="input-desc"),
            Label("Tab to move  /  Enter to add  /  Esc to close", id="dialog-hint"),
            id="dialog",
        )

    def on_mount(self) -> None:
        self.query_one("#input-name", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        name = self.query_one("#input-name", Input).value.strip()
        if not name:
            self.query_one("#input-name", Input).focus()
            return
        desc = self.query_one("#input-desc", Input).value.strip()
        self.dismiss((name, desc or None))

    def on_key(self, event) -> None:
        if event.key == "escape":
            event.stop()
            self.dismiss(None)


# ── Task Detail / Edit Modal ──────────────────────────────────────────────────

class TaskDetailModal(ModalScreen):
    DEFAULT_CSS = """
    TaskDetailModal { align: center middle; }
    #detail-dialog {
        width: 68; height: auto; background: $surface;
        border: thick $accent; padding: 1 2;
    }
    #detail-title { text-style: bold; margin-bottom: 1; }
    .field-label { color: $text-muted; margin-top: 1; }
    #detail-hint { color: $text-muted; margin-top: 1; text-align: right; }
    #detail-dialog Input { width: 100%; }
    """

    def __init__(self, task_id: str, content: str) -> None:
        super().__init__()
        self._task_id = task_id
        self._initial_content = content
        self._initial_desc: str | None = None

    def compose(self) -> ComposeResult:
        yield Container(
            Label("Edit Task", id="detail-title"),
            Label("Task Name *", classes="field-label"),
            Input(value=self._initial_content, id="detail-input-name"),
            Label("Description", classes="field-label"),
            Input(placeholder="Enter description...", id="detail-input-desc"),
            Label("Tab to move  /  Enter to save  /  Esc to cancel", id="detail-hint"),
            id="detail-dialog",
        )

    def on_mount(self) -> None:
        self.query_one("#detail-input-name", Input).focus()
        try:
            task = api_get_task(self._task_id)
            desc = task.get("description") or ""
            self._initial_desc = desc or None
            self.query_one("#detail-input-desc", Input).value = desc
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        name = self.query_one("#detail-input-name", Input).value.strip()
        if not name:
            self.query_one("#detail-input-name", Input).focus()
            return
        desc = self.query_one("#detail-input-desc", Input).value.strip()
        self.dismiss({
            "task_id": self._task_id,
            "content": name,
            "description": desc or None,
            "old_content": self._initial_content,
            "old_description": self._initial_desc,
        })

    def on_key(self, event) -> None:
        if event.key == "escape":
            event.stop()
            self.dismiss(None)


# ── Main App ──────────────────────────────────────────────────────────────────

class TodoistApp(App):
    """Todoist TUI"""

    TITLE = "Todoist"

    CSS = """
    Tree {
        width: 100%;
        height: 1fr;
        scrollbar-size: 1 1;
        padding: 0 1;
    }
    #status {
        height: 1;
        background: $panel;
        color: $text-muted;
        padding: 0 2;
    }
    #status.refreshing {
        background: $warning;
        color: $background;
    }
    #mode-indicator {
        height: 1;
        background: $panel;
        padding: 0 2;
    }
    #colon-input {
        display: none;
        height: 3;
        border: tall $accent;
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "handle_escape", "", show=False, priority=True),
        Binding("space", "space_key", "", show=False, priority=True),
        Binding("u", "undo", "Undo", show=False),
        Binding("ctrl+r", "redo", "Redo", show=False),
        Binding("ctrl+w", "collapse_others", "Collapse Others", show=False),
    ]

    def __init__(self, needs_update: bool = False) -> None:
        super().__init__()
        self.needs_update = needs_update
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self._mode: str = "normal"
        self._move_source_node = None
        self._move_source_data: dict = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield TaskTree("Projects", id="tree")
        yield Static("Loading...", id="status")
        yield Static("NORMAL", id="mode-indicator")
        yield Input(placeholder="command (e.g. 5g  mv)", id="colon-input")
        yield Footer()

    def on_mount(self) -> None:
        if self.needs_update:
            self.push_screen(UpdateModal(), self._after_update)
        else:
            self._load_projects()

    def _after_update(self, _result) -> None:
        self._load_projects()

    # ── Mode management ───────────────────────────────────────────────────────

    def _enter_normal_mode(self) -> None:
        self._mode = "normal"
        colon_input = self.query_one("#colon-input", Input)
        colon_input.display = False
        self.query_one("#tree", Tree).focus()
        self._update_mode_indicator()

    def _enter_command_mode(self) -> None:
        self._mode = "command"
        self._update_mode_indicator()
        self._set_status(
            "[a] Add  [Space] Complete  [r] Refresh  [e] Edit  [:] Command  [Esc] Cancel"
        )

    def _enter_colon_mode(self) -> None:
        self._mode = "colon"
        colon_input = self.query_one("#colon-input", Input)
        colon_input.display = True
        colon_input.value = ""
        colon_input.focus()
        self._update_mode_indicator()

    def _update_mode_indicator(self) -> None:
        indicator = self.query_one("#mode-indicator", Static)
        match self._mode:
            case "normal":
                indicator.update(Text("NORMAL", style="dim"))
            case "command":
                indicator.update(Text("-- COMMAND --", style="bold yellow"))
            case "colon":
                indicator.update(Text(":", style="bold cyan"))
            case "move":
                indicator.update(Text("-- MOVE --", style="bold red"))

    # ── Global key handling ───────────────────────────────────────────────────

    def action_handle_escape(self) -> None:
        # Skip if a modal is on top (modals handle their own Esc)
        if len(self.screen_stack) > 1:
            return
        match self._mode:
            case "normal":
                self._enter_command_mode()
            case "command":
                self._enter_normal_mode()
                self._restore_default_status()
            case "colon":
                self._enter_normal_mode()
                self._restore_default_status()
            case "move":
                self._cancel_move()

    def action_space_key(self) -> None:
        if len(self.screen_stack) > 1:
            return
        if self._mode == "command":
            self._enter_normal_mode()
            self._do_complete_task()

    def on_key(self, event) -> None:
        # Skip if modal is open
        if len(self.screen_stack) > 1:
            return

        colon_input = self.query_one("#colon-input", Input)

        # When colon input is visible, only intercept Esc
        if colon_input.display:
            if event.key == "escape":
                event.prevent_default()
                self._enter_normal_mode()
                self._restore_default_status()
            return

        tree = self.query_one("#tree", Tree)

        # j/k navigation works in all non-colon modes
        if event.key == "j":
            tree.action_cursor_down()
            return
        if event.key == "k":
            tree.action_cursor_up()
            return

        # Command mode key dispatch
        if self._mode == "command":
            match event.key:
                case "a":
                    self._enter_normal_mode()
                    self.action_add_task()
                case "r":
                    self._enter_normal_mode()
                    self.action_refresh()
                case "e":
                    self._enter_normal_mode()
                    self._do_edit_focused_task()
                case "colon":
                    self._enter_colon_mode()
                case _:
                    # Any other key exits command mode silently
                    if event.key != "escape":
                        self._enter_normal_mode()
                        self._restore_default_status()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "colon-input":
            return
        self._handle_colon_command(event.value.strip())

    def _handle_colon_command(self, cmd: str) -> None:
        self._enter_normal_mode()
        if not cmd:
            self._restore_default_status()
            return
        # :<n>g → jump to line
        if cmd.endswith("g"):
            try:
                line_num = int(cmd[:-1])
                self._jump_to_line(line_num)
            except ValueError:
                self._set_status(f"Invalid command: {cmd}")
            return
        # :mv → move mode
        if cmd == "mv":
            self._start_move_mode()
            return
        self._set_status(f"Unknown command: :{cmd}")

    def _jump_to_line(self, line_num: int) -> None:
        nodes = self._get_visible_nodes()
        if 1 <= line_num <= len(nodes):
            tree = self.query_one("#tree", Tree)
            tree.move_cursor(nodes[line_num - 1])
        else:
            self._set_status(f"Line {line_num} out of range (1–{len(nodes)})")

    # ── Load Projects ─────────────────────────────────────────────────────────

    def _load_projects(self) -> None:
        tree = self.query_one("#tree", Tree)
        tree.clear()
        tree.root.expand()
        self._set_status("Loading...")
        try:
            projects = api_get_projects()
        except Exception as e:
            self._set_status(f"Error: {e}")
            return

        for project in projects:
            base = Text(f"📋 {project['name']}")
            node = tree.root.add(
                base,
                data={"type": "project", "id": project["id"], "name": project["name"],
                      "base_label": base.copy()},
                expand=False,
            )
            node.add_leaf(
                Text("  Loading...", style="dim"),
                data={"type": "loading"},
            )
        self._renumber_nodes()
        self._restore_default_status()

    # ── Node Expand / Collapse Events ─────────────────────────────────────────

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        node = event.node
        data = node.data
        if not data or data["type"] != "project":
            return
        children = list(node.children)
        if children and children[0].data and children[0].data.get("type") != "loading":
            self._renumber_nodes()
            return
        self._load_project_content(node, data["id"])

    def on_tree_node_collapsed(self, event: Tree.NodeCollapsed) -> None:
        self._renumber_nodes()

    def _load_project_content(self, project_node, project_id: str) -> None:
        project_node.remove_children()
        try:
            sections = api_get_sections(project_id)
            tasks = api_get_tasks(project_id)
        except Exception as e:
            project_node.add_leaf(
                Text(f"  Error: {e}", style="red bold"),
                data={"type": "error"},
            )
            self._renumber_nodes()
            return
        self._build_tree_content(project_node, project_id, sections, tasks)

    def _build_tree_content(self, project_node, project_id: str,
                             sections: list, tasks: list) -> None:
        no_section_tasks = [t for t in tasks
                            if not t.get("section_id") and t.get("section_id") != 0]
        if no_section_tasks:
            ns_base = Text("  (No Section)", style="dim")
            ns_node = project_node.add(
                ns_base,
                data={"type": "section", "id": None, "name": "", "project_id": project_id,
                      "base_label": ns_base.copy()},
                expand=True,
            )
            for task in no_section_tasks:
                base = _clean_task_label(task["content"])
                ns_node.add_leaf(
                    base,
                    data={"type": "task", "id": task["id"], "content": task["content"],
                          "project_id": project_id, "section_id": None,
                          "order": task.get("order", 0), "base_label": base.copy()},
                )

        for section in sections:
            section_tasks = [t for t in tasks
                             if str(t.get("section_id", "")) == str(section["id"])]
            sec_base = Text(f"  📁 {section['name']}")
            if section_tasks:
                sec_base.append(f"  {len(section_tasks)}", style="dim")
            sec_node = project_node.add(
                sec_base,
                data={"type": "section", "id": section["id"], "name": section["name"],
                      "project_id": project_id, "base_label": sec_base.copy()},
                expand=True,
            )
            for task in section_tasks:
                base = _clean_task_label(task["content"])
                sec_node.add_leaf(
                    base,
                    data={"type": "task", "id": task["id"], "content": task["content"],
                          "project_id": project_id, "section_id": section["id"],
                          "order": task.get("order", 0), "base_label": base.copy()},
                )

        if not sections and not tasks:
            project_node.add_leaf(
                Text("  No tasks", style="dim"),
                data={"type": "empty"},
            )

        self._renumber_nodes()

    # ── Node Select Event ─────────────────────────────────────────────────────

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        data = event.node.data
        if not data:
            return
        if self._mode != "normal":
            return
        match data["type"]:
            case "project":
                self._set_status(
                    f"📋 {data['name']}  |  [Esc] command mode  [r] refresh  [ctrl+w] collapse"
                )
            case "section":
                name = data["name"] or "No Section"
                self._set_status(f"📁 {name}  |  [Esc] command mode")
            case "task":
                self._set_status(
                    f"○ {data['content']}  |  [Esc→e] edit  [Esc→Space] complete  [Esc→:mv] move"
                )
            case _:
                self._restore_default_status()

    # ── TaskActivated (Enter on task node) ────────────────────────────────────

    def on_task_tree_task_activated(self, event: TaskTree.TaskActivated) -> None:
        if self._mode == "move":
            self._execute_move(event.node, event.node_data)
        # In other modes, Enter on a task does nothing (use Esc→e to edit)

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_add_task(self) -> None:
        project_id, section_id, location = self._get_context()
        if not project_id:
            self._set_status("Select a location to add a task")
            return
        target_node = self._find_section_node(project_id, section_id)

        def on_dismiss(result: tuple[str, str | None] | None) -> None:
            if not result:
                return
            content, description = result
            if target_node is not None:
                base = _clean_task_label(content)
                placeholder = target_node.add_leaf(
                    base,
                    data={"type": "task", "id": None, "content": content,
                          "project_id": project_id, "section_id": section_id,
                          "order": 0, "pending": True, "base_label": base.copy()},
                )
                self._renumber_nodes()
                self._add_task_worker(placeholder, content, description, project_id, section_id)
            else:
                try:
                    task = api_add_task(content, project_id, section_id, description)
                except Exception as e:
                    self._set_status(f"Error: {e}")
                    return
                task_id = task["id"]
                self._undo_stack.append({
                    "description": f"Add task: {content}",
                    "undo_fn": lambda: api_delete_task(task_id),
                    "redo_fn": lambda: api_add_task(content, project_id, section_id, description),
                    "project_id": project_id,
                })
                self._redo_stack.clear()
                self._refresh_project_by_id(project_id)

        self.push_screen(AddTaskModal(project_id, section_id, location), on_dismiss)

    @work(thread=True)
    def _add_task_worker(self, placeholder, content: str, description: str | None,
                          project_id: str, section_id: str | None) -> None:
        try:
            task = api_add_task(content, project_id, section_id, description)
            self.call_from_thread(
                self._on_add_success, placeholder, task, content, description, project_id, section_id
            )
        except Exception as e:
            self.call_from_thread(self._on_add_error, placeholder, str(e))

    def _on_add_success(self, placeholder, task: dict, content: str,
                         description: str | None, project_id: str, section_id: str | None) -> None:
        task_id = task["id"]
        try:
            placeholder.data.update({"id": task_id, "pending": False,
                                     "order": task.get("order", 0)})
        except Exception:
            pass
        self._undo_stack.append({
            "description": f"Add task: {content}",
            "undo_fn": lambda: api_delete_task(task_id),
            "redo_fn": lambda: api_add_task(content, project_id, section_id, description),
            "project_id": project_id,
        })
        self._redo_stack.clear()
        self._renumber_nodes()

    def _on_add_error(self, placeholder, error: str) -> None:
        try:
            placeholder.remove()
        except Exception:
            pass
        self._renumber_nodes()
        self._set_status(f"Error: {error}")

    def _do_complete_task(self) -> None:
        tree = self.query_one("#tree", Tree)
        node = tree.cursor_node
        if not node or not node.data or node.data["type"] != "task":
            self._set_status("Select a task to complete")
            return
        if node.data.get("pending"):
            return
        task_id = node.data["id"]
        content = node.data["content"]
        project_id = node.data["project_id"]
        node.data["pending"] = True
        self._renumber_nodes()
        self._complete_task_worker(node, task_id, content, project_id)

    @work(thread=True)
    def _complete_task_worker(self, node, task_id: str, content: str, project_id: str) -> None:
        try:
            api_close_task(task_id)
            self.call_from_thread(self._on_complete_success, node, task_id, content, project_id)
        except Exception as e:
            self.call_from_thread(self._on_complete_error, node, content, str(e))

    def _on_complete_success(self, node, task_id: str, content: str, project_id: str) -> None:
        self._undo_stack.append({
            "description": f"Complete task: {content}",
            "undo_fn": lambda: api_reopen_task(task_id),
            "redo_fn": lambda: api_close_task(task_id),
            "project_id": project_id,
        })
        self._redo_stack.clear()
        try:
            node.remove()
        except Exception:
            pass
        self._renumber_nodes()

    def _on_complete_error(self, node, content: str, error: str) -> None:
        try:
            node.data["pending"] = False
        except Exception:
            pass
        self._renumber_nodes()
        self._set_status(f"Error: {error}")

    def _do_edit_focused_task(self) -> None:
        tree = self.query_one("#tree", Tree)
        node = tree.cursor_node
        if not node or not node.data or node.data.get("type") != "task":
            self._set_status("Select a task to edit")
            return
        if node.data.get("pending"):
            return
        self._open_task_detail(node, node.data)

    def _open_task_detail(self, task_node, task_data: dict) -> None:
        def on_detail_dismiss(result: dict | None) -> None:
            if not result:
                return
            task_id = result["task_id"]
            new_content = result["content"]
            new_desc = result["description"]
            old_content = result["old_content"]
            old_desc = result["old_description"]
            project_id = task_data["project_id"]
            try:
                task_node.data["pending"] = True
                new_base = _clean_task_label(new_content)
                task_node.data["base_label"] = new_base.copy()
            except Exception:
                pass
            self._renumber_nodes()
            self._edit_task_worker(
                task_node, task_id, new_content, new_desc, old_content, old_desc, project_id
            )

        self.push_screen(TaskDetailModal(task_data["id"], task_data["content"]), on_detail_dismiss)

    @work(thread=True)
    def _edit_task_worker(self, node, task_id: str, new_content: str, new_desc: str | None,
                           old_content: str, old_desc: str | None, project_id: str) -> None:
        try:
            api_update_task(task_id, new_content, new_desc)
            self.call_from_thread(
                self._on_edit_success, node, task_id, new_content, new_desc,
                old_content, old_desc, project_id
            )
        except Exception as e:
            self.call_from_thread(self._on_edit_error, node, old_content, str(e))

    def _on_edit_success(self, node, task_id: str, new_content: str, new_desc: str | None,
                          old_content: str, old_desc: str | None, project_id: str) -> None:
        try:
            node.data.update({"content": new_content, "pending": False})
            node.data["base_label"] = _clean_task_label(new_content).copy()
        except Exception:
            pass
        self._renumber_nodes()
        self._undo_stack.append({
            "description": f"Update task: {old_content}",
            "undo_fn": lambda: api_update_task(task_id, old_content, old_desc),
            "redo_fn": lambda: api_update_task(task_id, new_content, new_desc),
            "project_id": project_id,
        })
        self._redo_stack.clear()

    def _on_edit_error(self, node, old_content: str, error: str) -> None:
        try:
            node.data["pending"] = False
            node.data["base_label"] = _clean_task_label(old_content).copy()
        except Exception:
            pass
        self._renumber_nodes()
        self._set_status(f"Error: {error}")

    # ── Move mode ─────────────────────────────────────────────────────────────

    def _start_move_mode(self) -> None:
        tree = self.query_one("#tree", Tree)
        node = tree.cursor_node
        if not node or not node.data or node.data.get("type") != "task":
            self._set_status("Select a task to move")
            return
        if node.data.get("pending"):
            return
        self._mode = "move"
        self._move_source_node = node
        self._move_source_data = dict(node.data)
        node.data["moving"] = True
        self._renumber_nodes()
        self._update_mode_indicator()
        self._set_status(
            f"Moving: {node.data['content']}  |  navigate to destination → [Enter]  [Esc] cancel"
        )

    def _cancel_move(self) -> None:
        if self._move_source_node:
            try:
                self._move_source_node.data.pop("moving", None)
            except Exception:
                pass
        self._move_source_node = None
        self._move_source_data = {}
        self._enter_normal_mode()
        self._renumber_nodes()
        self._restore_default_status()

    def _execute_move(self, dest_node, dest_data: dict) -> None:
        src_node = self._move_source_node
        src_data = self._move_source_data
        if not src_node:
            self._cancel_move()
            return
        if dest_data.get("type") != "task":
            self._set_status("Select a task as the destination")
            return
        if src_data.get("id") == dest_data.get("id"):
            self._cancel_move()
            return

        dest_project_id = dest_data["project_id"]
        dest_section_id = dest_data.get("section_id")
        src_task_id = src_data["id"]
        src_content = src_data["content"]
        orig_project_id = src_data["project_id"]

        try:
            src_node.data.pop("moving", None)
        except Exception:
            pass
        self._move_source_node = None
        self._move_source_data = {}
        self._enter_normal_mode()

        src_node.data["pending"] = True
        self._renumber_nodes()
        self._set_status(f"Moving {src_content}...")

        self._move_task_worker(
            src_node, src_task_id, src_content,
            orig_project_id, dest_project_id, dest_section_id
        )

    @work(thread=True)
    def _move_task_worker(self, src_node, task_id: str, content: str, orig_project_id: str,
                           dest_project_id: str, dest_section_id: str | None) -> None:
        try:
            api_move_task(task_id, dest_section_id, dest_project_id)
            self.call_from_thread(
                self._on_move_success, src_node, orig_project_id, dest_project_id
            )
        except Exception as e:
            self.call_from_thread(self._on_move_error, src_node, str(e))

    def _on_move_success(self, src_node, orig_project_id: str, dest_project_id: str) -> None:
        try:
            src_node.data["pending"] = False
        except Exception:
            pass
        self._refresh_project_by_id(dest_project_id)
        if orig_project_id != dest_project_id:
            self._refresh_project_by_id(orig_project_id)

    def _on_move_error(self, src_node, error: str) -> None:
        try:
            src_node.data["pending"] = False
        except Exception:
            pass
        self._renumber_nodes()
        self._set_status(f"Move failed: {error}")

    # ── Refresh ───────────────────────────────────────────────────────────────

    def action_refresh(self) -> None:
        tree = self.query_one("#tree", Tree)
        expanded_ids = {
            child.data["id"]
            for child in tree.root.children
            if child.data and child.data.get("type") == "project" and child.is_expanded
        }
        status = self.query_one("#status", Static)
        status.add_class("refreshing")
        self._set_status("🔄 Refreshing...")
        self._full_refresh_worker(expanded_ids)

    @work(thread=True)
    def _full_refresh_worker(self, expanded_ids: set) -> None:
        try:
            projects = api_get_projects()
            project_data: dict = {}
            for pid in expanded_ids:
                project_data[pid] = (api_get_sections(pid), api_get_tasks(pid))
            self.call_from_thread(self._apply_full_refresh, projects, project_data, None)
        except Exception as e:
            self.call_from_thread(self._apply_full_refresh, None, {}, str(e))

    def _apply_full_refresh(self, projects: list | None, project_data: dict,
                              error: str | None) -> None:
        status = self.query_one("#status", Static)
        status.remove_class("refreshing")
        if error:
            self._set_status(f"Error: {error}")
            return
        tree = self.query_one("#tree", Tree)
        tree.clear()
        tree.root.expand()
        for project in (projects or []):
            pid = project["id"]
            base = Text(f"📋 {project['name']}")
            node = tree.root.add(
                base,
                data={"type": "project", "id": pid, "name": project["name"],
                      "base_label": base.copy()},
                expand=False,
            )
            if pid in project_data:
                sections, tasks = project_data[pid]
                self._build_tree_content(node, pid, sections, tasks)
                node.expand()
            else:
                node.add_leaf(Text("  Loading...", style="dim"), data={"type": "loading"})
        self._renumber_nodes()
        self._restore_default_status()

    # ── Undo / Redo ───────────────────────────────────────────────────────────

    def action_undo(self) -> None:
        if not self._undo_stack:
            self._set_status("Nothing to undo")
            return
        entry = self._undo_stack.pop()
        try:
            entry["undo_fn"]()
        except Exception as e:
            self._set_status(f"Undo failed: {e}")
            return
        self._redo_stack.append(entry)
        self._set_status(f"Undone: {entry['description']}")
        self._refresh_project_by_id(entry["project_id"])

    def action_redo(self) -> None:
        if not self._redo_stack:
            self._set_status("Nothing to redo")
            return
        entry = self._redo_stack.pop()
        try:
            entry["redo_fn"]()
        except Exception as e:
            self._set_status(f"Redo failed: {e}")
            return
        self._undo_stack.append(entry)
        self._set_status(f"Redone: {entry['description']}")
        self._refresh_project_by_id(entry["project_id"])

    # ── Collapse Others ───────────────────────────────────────────────────────

    def action_collapse_others(self) -> None:
        tree = self.query_one("#tree", Tree)
        node = tree.cursor_node
        if not node:
            return
        current = node
        while current and current.data and current.data.get("type") != "section":
            current = current.parent
        if not current or not current.data or current.data.get("type") != "section":
            self._set_status("No section selected")
            return
        section_node = current
        project_node = section_node.parent
        if not project_node:
            return
        for child in project_node.children:
            if child is not section_node:
                child.collapse()
        self._renumber_nodes()

    # ── Renumber ──────────────────────────────────────────────────────────────

    def _get_visible_nodes(self) -> list:
        tree = self.query_one("#tree", Tree)
        nodes = []

        def walk(node) -> None:
            for child in node.children:
                data = child.data
                if data and data.get("type") not in ("loading", "error", "empty"):
                    nodes.append(child)
                if child.is_expanded:
                    walk(child)

        walk(tree.root)
        return nodes

    def _renumber_nodes(self) -> None:
        nodes = self._get_visible_nodes()
        for i, node in enumerate(nodes, start=1):
            base = node.data.get("base_label") if node.data else None
            if base is None:
                continue
            pending = node.data.get("pending", False)
            moving = node.data.get("moving", False)
            node.set_label(_build_displayed_label(base, i, pending, moving))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    def _restore_default_status(self) -> None:
        self._set_status(
            "Expand a project  |  [Esc] command mode  |  j/k navigate  |  [q] quit"
        )

    def _get_context(self) -> tuple[str | None, str | None, str]:
        tree = self.query_one("#tree", Tree)
        node = tree.cursor_node
        if not node or not node.data:
            return None, None, ""
        data = node.data
        match data["type"]:
            case "project":
                return data["id"], None, data["name"]
            case "section":
                return data["project_id"], data["id"], data["name"] or "No Section"
            case "task":
                return data["project_id"], data.get("section_id"), ""
            case _:
                return None, None, ""

    def _find_section_node(self, project_id: str, section_id: str | None):
        tree = self.query_one("#tree", Tree)
        for proj_node in tree.root.children:
            if not (proj_node.data and proj_node.data.get("id") == project_id):
                continue
            for sec_node in proj_node.children:
                if sec_node.data and sec_node.data.get("type") == "section":
                    node_sid = sec_node.data.get("id")
                    if str(node_sid or "") == str(section_id or ""):
                        return sec_node
        return None

    def _get_project_node(self):
        tree = self.query_one("#tree", Tree)
        node = tree.cursor_node
        if not node:
            return None
        current = node
        while current and current.data and current.data.get("type") != "project":
            current = current.parent
        if current and current.data and current.data.get("type") == "project":
            return current
        return None

    def _force_reload(self, project_node) -> None:
        project_node.remove_children()
        project_node.add_leaf(
            Text("  Loading...", style="dim"),
            data={"type": "loading"},
        )
        self._load_project_content(project_node, project_node.data["id"])

    def _refresh_project_by_id(self, project_id: str) -> None:
        tree = self.query_one("#tree", Tree)
        for child in tree.root.children:
            if child.data and child.data.get("id") == project_id:
                self._force_reload(child)
                return


# ── Entry Point ───────────────────────────────────────────────────────────────

def run_tui() -> None:
    needs_update = _needs_update()
    TodoistApp(needs_update=needs_update).run()
