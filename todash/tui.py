from __future__ import annotations

import os

import requests
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Static

TOKEN: str | None = None
BASE_URL = "https://api.todoist.com/api/v1"

try:
    TTY = int(os.getenv("TTY", "3600"))
except ValueError:
    TTY = 3600


# ── API ───────────────────────────────────────────────────────────────────────

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


# ── Row rendering ─────────────────────────────────────────────────────────────

def _render_row(node: dict, line_num: int) -> Text:
    """Render a list row with line number at the far left."""
    num = Text(f"{line_num:>3}│", style="dim cyan")
    ntype = node.get("type")
    if ntype == "project":
        icon = "▼ " if node.get("expanded") else "▶ "
        c = Text(f" {icon}📋 {node['name']}")
    elif ntype == "section":
        icon = "▼ " if node.get("expanded", True) else "▶ "
        name = node.get("name") or "No Section"
        c = Text(f"   {icon}📁 {name}")
    elif ntype == "task":
        c = Text(f"       ○ {node['content']}")
        if node.get("moving"):
            c.stylize("bold yellow")
        elif node.get("pending"):
            c.stylize("dim")
    else:
        return Text("")
    return Text.assemble(num, c)


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

    TITLE = "Todash"

    CSS = """
    ListView {
        width: 100%;
        height: 1fr;
        scrollbar-size: 1 1;
        padding: 0;
    }
    ListView > ListItem {
        padding: 0;
        height: 1;
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

    def __init__(self) -> None:
        super().__init__()
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self._mode: str = "normal"
        self._move_source_data: dict = {}
        self._projects_data: list[dict] = []
        self._flat_nodes: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield ListView(id="list")
        yield Static("Loading...", id="status")
        yield Static("NORMAL", id="mode-indicator")
        yield Input(placeholder="command (e.g. 5g  mv)", id="colon-input")
        yield Footer()

    def on_mount(self) -> None:
        self._load_projects()

    def _lv(self) -> ListView:
        return self.query_one("#list", ListView)

    def _get_current_node(self) -> dict | None:
        idx = self._lv().index
        if idx is None or idx >= len(self._flat_nodes):
            return None
        return self._flat_nodes[idx]

    def _rebuild_list(self) -> None:
        """Flatten _projects_data into _flat_nodes and repopulate ListView."""
        lv = self._lv()
        old_idx = lv.index

        self._flat_nodes = []
        items: list[ListItem] = []

        for proj in self._projects_data:
            self._flat_nodes.append(proj)
            items.append(ListItem(Label(_render_row(proj, len(self._flat_nodes)))))

            if not proj.get("expanded"):
                continue

            if not proj.get("loaded"):
                placeholder: dict = {"type": "_loading"}
                self._flat_nodes.append(placeholder)
                items.append(ListItem(Label(Text("      Loading...", style="dim"))))
                continue

            for sec in proj.get("sections", []):
                self._flat_nodes.append(sec)
                items.append(ListItem(Label(_render_row(sec, len(self._flat_nodes)))))

                if not sec.get("expanded", True):
                    continue

                for task in sec.get("tasks", []):
                    self._flat_nodes.append(task)
                    items.append(ListItem(Label(_render_row(task, len(self._flat_nodes)))))

        lv.clear()
        for item in items:
            lv.append(item)

        if old_idx is not None and old_idx < len(self._flat_nodes):
            lv.index = old_idx
        elif self._flat_nodes:
            lv.index = 0

    # ── Mode management ───────────────────────────────────────────────────────

    def _enter_normal_mode(self) -> None:
        self._mode = "normal"
        colon_input = self.query_one("#colon-input", Input)
        colon_input.display = False
        self._lv().focus()
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
        if len(self.screen_stack) > 1:
            return

        colon_input = self.query_one("#colon-input", Input)

        if colon_input.display:
            if event.key == "escape":
                event.prevent_default()
                self._enter_normal_mode()
                self._restore_default_status()
            return

        lv = self._lv()

        if event.key == "j":
            lv.action_cursor_down()
            return
        if event.key == "k":
            lv.action_cursor_up()
            return

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
        if cmd.endswith("g"):
            try:
                line_num = int(cmd[:-1])
                self._jump_to_line(line_num)
            except ValueError:
                self._set_status(f"Invalid command: {cmd}")
            return
        if cmd == "mv":
            self._start_move_mode()
            return
        self._set_status(f"Unknown command: :{cmd}")

    def _jump_to_line(self, line_num: int) -> None:
        total = len(self._flat_nodes)
        if 1 <= line_num <= total:
            self._lv().index = line_num - 1
        else:
            self._set_status(f"Line {line_num} out of range (1–{total})")

    # ── List events ───────────────────────────────────────────────────────────

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Enter on a list item — expand/collapse or move."""
        if len(self.screen_stack) > 1:
            return
        node = self._get_current_node()
        if not node:
            return
        ntype = node.get("type")
        if ntype == "project":
            self._toggle_project(node)
        elif ntype == "section":
            node["expanded"] = not node.get("expanded", True)
            self._rebuild_list()
        elif ntype == "task":
            if self._mode == "move":
                self._execute_move(node)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Update status bar when cursor moves."""
        if self._mode != "normal":
            return
        node = self._get_current_node()
        if not node:
            return
        match node.get("type"):
            case "project":
                self._set_status(
                    f"📋 {node['name']}  |  [Esc] command mode  [r] refresh  [ctrl+w] collapse"
                )
            case "section":
                name = node.get("name") or "No Section"
                self._set_status(f"📁 {name}  |  [Esc] command mode")
            case "task":
                self._set_status(
                    f"○ {node['content']}  |  [Esc→e] edit  [Esc→Space] complete  [Esc→:mv] move"
                )
            case _:
                self._restore_default_status()

    def _toggle_project(self, proj: dict) -> None:
        if proj.get("expanded"):
            proj["expanded"] = False
            self._rebuild_list()
        else:
            proj["expanded"] = True
            if not proj.get("loaded"):
                self._rebuild_list()
                self._load_project_content(proj)
            else:
                self._rebuild_list()

    # ── Load Projects ─────────────────────────────────────────────────────────

    def _load_projects(self) -> None:
        self._set_status("Loading...")
        try:
            projects = api_get_projects()
        except Exception as e:
            self._set_status(f"Error: {e}")
            return

        self._projects_data = [
            {"type": "project", "id": p["id"], "name": p["name"],
             "expanded": False, "loaded": False, "sections": []}
            for p in projects
        ]
        self._rebuild_list()
        self._restore_default_status()

    def _load_project_content(self, proj: dict) -> None:
        """Fetch and populate project content, then rebuild list."""
        try:
            sections = api_get_sections(proj["id"])
            tasks = api_get_tasks(proj["id"])
        except Exception as e:
            self._set_status(f"Error loading {proj['name']}: {e}")
            proj["loaded"] = True
            self._rebuild_list()
            return
        self._populate_project(proj, sections, tasks)
        self._rebuild_list()

    def _populate_project(self, proj: dict, sections: list, tasks: list) -> None:
        """Populate proj['sections'] from API data. Does NOT rebuild list."""
        project_id = proj["id"]
        result_sections: list[dict] = []

        no_section_tasks = [t for t in tasks
                            if not t.get("section_id") and t.get("section_id") != 0]
        if no_section_tasks:
            result_sections.append({
                "type": "section", "id": None, "name": "", "project_id": project_id,
                "expanded": True,
                "tasks": [
                    {"type": "task", "id": t["id"], "content": t["content"],
                     "project_id": project_id, "section_id": None,
                     "order": t.get("order", 0), "pending": False, "moving": False}
                    for t in no_section_tasks
                ],
            })

        for sec in sections:
            section_tasks = [t for t in tasks
                             if str(t.get("section_id", "")) == str(sec["id"])]
            result_sections.append({
                "type": "section", "id": sec["id"], "name": sec["name"],
                "project_id": project_id, "expanded": True,
                "tasks": [
                    {"type": "task", "id": t["id"], "content": t["content"],
                     "project_id": project_id, "section_id": sec["id"],
                     "order": t.get("order", 0), "pending": False, "moving": False}
                    for t in section_tasks
                ],
            })

        proj["sections"] = result_sections
        proj["loaded"] = True

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_add_task(self) -> None:
        project_id, section_id, location = self._get_context()
        if not project_id:
            self._set_status("Select a location to add a task")
            return
        sec_data = self._find_section_in_data(project_id, section_id)

        def on_dismiss(result: tuple[str, str | None] | None) -> None:
            if not result:
                return
            content, description = result
            if sec_data is not None:
                task_dict: dict = {
                    "type": "task", "id": None, "content": content,
                    "project_id": project_id, "section_id": section_id,
                    "order": 0, "pending": True, "moving": False,
                }
                sec_data["tasks"].append(task_dict)
                self._rebuild_list()
                self._add_task_worker(task_dict, content, description, project_id, section_id)
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
    def _add_task_worker(self, task_dict: dict, content: str, description: str | None,
                          project_id: str, section_id: str | None) -> None:
        try:
            task = api_add_task(content, project_id, section_id, description)
            self.call_from_thread(
                self._on_add_success, task_dict, task, content, description, project_id, section_id
            )
        except Exception as e:
            self.call_from_thread(self._on_add_error, task_dict, str(e))

    def _on_add_success(self, task_dict: dict, task: dict, content: str,
                         description: str | None, project_id: str, section_id: str | None) -> None:
        task_id = task["id"]
        task_dict.update({"id": task_id, "pending": False, "order": task.get("order", 0)})
        self._undo_stack.append({
            "description": f"Add task: {content}",
            "undo_fn": lambda: api_delete_task(task_id),
            "redo_fn": lambda: api_add_task(content, project_id, section_id, description),
            "project_id": project_id,
        })
        self._redo_stack.clear()
        self._rebuild_list()

    def _on_add_error(self, task_dict: dict, error: str) -> None:
        self._remove_task_from_data(task_dict)
        self._rebuild_list()
        self._set_status(f"Error: {error}")

    def _do_complete_task(self) -> None:
        node = self._get_current_node()
        if not node or node.get("type") != "task":
            self._set_status("Select a task to complete")
            return
        if node.get("pending"):
            return
        task_id = node["id"]
        content = node["content"]
        project_id = node["project_id"]
        node["pending"] = True
        self._rebuild_list()
        self._complete_task_worker(node, task_id, content, project_id)

    @work(thread=True)
    def _complete_task_worker(self, task_dict: dict, task_id: str,
                               content: str, project_id: str) -> None:
        try:
            api_close_task(task_id)
            self.call_from_thread(self._on_complete_success, task_dict, task_id, content, project_id)
        except Exception as e:
            self.call_from_thread(self._on_complete_error, task_dict, content, str(e))

    def _on_complete_success(self, task_dict: dict, task_id: str,
                              content: str, project_id: str) -> None:
        self._undo_stack.append({
            "description": f"Complete task: {content}",
            "undo_fn": lambda: api_reopen_task(task_id),
            "redo_fn": lambda: api_close_task(task_id),
            "project_id": project_id,
        })
        self._redo_stack.clear()
        self._remove_task_from_data(task_dict)
        self._rebuild_list()

    def _on_complete_error(self, task_dict: dict, content: str, error: str) -> None:
        task_dict["pending"] = False
        self._rebuild_list()
        self._set_status(f"Error: {error}")

    def _do_edit_focused_task(self) -> None:
        node = self._get_current_node()
        if not node or node.get("type") != "task":
            self._set_status("Select a task to edit")
            return
        if node.get("pending"):
            return
        self._open_task_detail(node)

    def _open_task_detail(self, task_dict: dict) -> None:
        def on_detail_dismiss(result: dict | None) -> None:
            if not result:
                return
            task_id = result["task_id"]
            new_content = result["content"]
            new_desc = result["description"]
            old_content = result["old_content"]
            old_desc = result["old_description"]
            project_id = task_dict["project_id"]
            task_dict["pending"] = True
            task_dict["content"] = new_content
            self._rebuild_list()
            self._edit_task_worker(
                task_dict, task_id, new_content, new_desc, old_content, old_desc, project_id
            )

        self.push_screen(TaskDetailModal(task_dict["id"], task_dict["content"]), on_detail_dismiss)

    @work(thread=True)
    def _edit_task_worker(self, task_dict: dict, task_id: str, new_content: str,
                           new_desc: str | None, old_content: str, old_desc: str | None,
                           project_id: str) -> None:
        try:
            api_update_task(task_id, new_content, new_desc)
            self.call_from_thread(
                self._on_edit_success, task_dict, task_id, new_content, new_desc,
                old_content, old_desc, project_id
            )
        except Exception as e:
            self.call_from_thread(self._on_edit_error, task_dict, old_content, str(e))

    def _on_edit_success(self, task_dict: dict, task_id: str, new_content: str,
                          new_desc: str | None, old_content: str, old_desc: str | None,
                          project_id: str) -> None:
        task_dict.update({"content": new_content, "pending": False})
        self._rebuild_list()
        self._undo_stack.append({
            "description": f"Update task: {old_content}",
            "undo_fn": lambda: api_update_task(task_id, old_content, old_desc),
            "redo_fn": lambda: api_update_task(task_id, new_content, new_desc),
            "project_id": project_id,
        })
        self._redo_stack.clear()

    def _on_edit_error(self, task_dict: dict, old_content: str, error: str) -> None:
        task_dict["pending"] = False
        task_dict["content"] = old_content
        self._rebuild_list()
        self._set_status(f"Error: {error}")

    # ── Move mode ─────────────────────────────────────────────────────────────

    def _start_move_mode(self) -> None:
        node = self._get_current_node()
        if not node or node.get("type") != "task":
            self._set_status("Select a task to move")
            return
        if node.get("pending"):
            return
        self._mode = "move"
        self._move_source_data = node
        node["moving"] = True
        self._rebuild_list()
        self._update_mode_indicator()
        self._set_status(
            f"Moving: {node['content']}  |  navigate to destination → [Enter]  [Esc] cancel"
        )

    def _cancel_move(self) -> None:
        if self._move_source_data:
            self._move_source_data.pop("moving", None)
        self._move_source_data = {}
        self._enter_normal_mode()
        self._rebuild_list()
        self._restore_default_status()

    def _execute_move(self, dest_dict: dict) -> None:
        src_data = self._move_source_data
        if not src_data:
            self._cancel_move()
            return
        if dest_dict.get("type") != "task":
            self._set_status("Select a task as the destination")
            return
        if src_data.get("id") == dest_dict.get("id"):
            self._cancel_move()
            return

        dest_project_id = dest_dict["project_id"]
        dest_section_id = dest_dict.get("section_id")
        src_task_id = src_data["id"]
        src_content = src_data["content"]
        orig_project_id = src_data["project_id"]

        src_data.pop("moving", None)
        self._move_source_data = {}
        self._enter_normal_mode()

        src_data["pending"] = True
        self._rebuild_list()
        self._set_status(f"Moving {src_content}...")

        self._move_task_worker(
            src_data, src_task_id, src_content,
            orig_project_id, dest_project_id, dest_section_id
        )

    @work(thread=True)
    def _move_task_worker(self, src_dict: dict, task_id: str, content: str,
                           orig_project_id: str, dest_project_id: str,
                           dest_section_id: str | None) -> None:
        try:
            api_move_task(task_id, dest_section_id, dest_project_id)
            self.call_from_thread(
                self._on_move_success, src_dict, orig_project_id, dest_project_id
            )
        except Exception as e:
            self.call_from_thread(self._on_move_error, src_dict, str(e))

    def _on_move_success(self, src_dict: dict, orig_project_id: str, dest_project_id: str) -> None:
        src_dict["pending"] = False
        self._refresh_project_by_id(dest_project_id)
        if orig_project_id != dest_project_id:
            self._refresh_project_by_id(orig_project_id)

    def _on_move_error(self, src_dict: dict, error: str) -> None:
        src_dict["pending"] = False
        self._rebuild_list()
        self._set_status(f"Move failed: {error}")

    # ── Refresh ───────────────────────────────────────────────────────────────

    def action_refresh(self) -> None:
        expanded_ids = {p["id"] for p in self._projects_data if p.get("expanded")}
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

        new_projects: list[dict] = []
        for p in (projects or []):
            pid = p["id"]
            proj_dict: dict = {
                "type": "project", "id": pid, "name": p["name"],
                "expanded": False, "loaded": False, "sections": [],
            }
            if pid in project_data:
                sections, tasks = project_data[pid]
                proj_dict["expanded"] = True
                self._populate_project(proj_dict, sections, tasks)
            new_projects.append(proj_dict)

        self._projects_data = new_projects
        self._rebuild_list()
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
        node = self._get_current_node()
        if not node:
            return
        cur_sec: dict | None = None
        if node.get("type") == "section":
            cur_sec = node
        elif node.get("type") == "task":
            for proj in self._projects_data:
                for sec in proj.get("sections", []):
                    if node in sec["tasks"]:
                        cur_sec = sec
                        break
        if not cur_sec:
            self._set_status("No section selected")
            return
        project_id = cur_sec["project_id"]
        for proj in self._projects_data:
            if proj["id"] == project_id:
                for sec in proj.get("sections", []):
                    if sec is not cur_sec:
                        sec["expanded"] = False
        self._rebuild_list()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    def _restore_default_status(self) -> None:
        self._set_status(
            "Expand a project  |  [Esc] command mode  |  j/k navigate  |  [q] quit"
        )

    def _get_context(self) -> tuple[str | None, str | None, str]:
        node = self._get_current_node()
        if not node:
            return None, None, ""
        match node.get("type"):
            case "project":
                return node["id"], None, node["name"]
            case "section":
                return node["project_id"], node.get("id"), node.get("name") or "No Section"
            case "task":
                return node["project_id"], node.get("section_id"), ""
            case _:
                return None, None, ""

    def _find_section_in_data(self, project_id: str, section_id: str | None) -> dict | None:
        for proj in self._projects_data:
            if proj["id"] != project_id:
                continue
            for sec in proj.get("sections", []):
                if str(sec.get("id") or "") == str(section_id or ""):
                    return sec
        return None

    def _remove_task_from_data(self, task_dict: dict) -> None:
        for proj in self._projects_data:
            for sec in proj.get("sections", []):
                if task_dict in sec["tasks"]:
                    sec["tasks"].remove(task_dict)
                    return

    def _refresh_project_by_id(self, project_id: str) -> None:
        for proj in self._projects_data:
            if proj["id"] == project_id:
                if proj.get("expanded"):
                    proj["loaded"] = False
                    proj["sections"] = []
                    self._rebuild_list()
                    self._load_project_content(proj)
                else:
                    self._rebuild_list()
                return
        self._rebuild_list()


# ── Entry Point ───────────────────────────────────────────────────────────────

def run_tui() -> None:
    global TOKEN
    TOKEN = os.getenv("TODOIST_TOKEN")
    TodoistApp().run()
