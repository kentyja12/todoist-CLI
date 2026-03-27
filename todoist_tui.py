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


# ── 更新チェック ──────────────────────────────────────────────────────────────

def _needs_update() -> bool:
    """前回の更新から TTY 秒以上経過しているか確認"""
    if not LAST_UPDATE_FILE.exists():
        return True
    try:
        last = float(LAST_UPDATE_FILE.read_text().strip())
        return (time.time() - last) >= TTY
    except ValueError:
        return True  # 旧フォーマット（日付文字列）なら強制更新


def _write_last_update() -> None:
    LAST_UPDATE_FILE.write_text(str(time.time()))


# ── API ──────────────────────────────────────────────────────────────────────

def _headers() -> dict:
    return {"Authorization": f"Bearer {TOKEN}"}


def _get(path: str, params: dict | None = None) -> list:
    """ページネーションを自動的に処理して全件返す"""
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


# ── カスタムTree ─────────────────────────────────────────────────────────────

class TaskTree(Tree):
    """タスクノード上で Enter を押すと OpenTask メッセージを発行するカスタム Tree。
    App レベルの priority バインドを使わないため、モーダル内の Enter と競合しない。"""

    class OpenTask(Message):
        def __init__(self, node_data: dict) -> None:
            super().__init__()
            self.node_data = node_data

    def on_key(self, event) -> None:
        if event.key == "enter":
            node = self.cursor_node
            if node and node.data and node.data.get("type") == "task":
                event.prevent_default()
                self.post_message(TaskTree.OpenTask(node.data))
            # task 以外（project/section）は Tree デフォルトの展開/折り畳みに委譲


# ── 更新モーダル ──────────────────────────────────────────────────────────────

class UpdateModal(ModalScreen):
    """git pull を実行する更新モーダル。Esc / q 以外の操作はすべて無効。"""

    BINDINGS = [
        Binding("escape", "cancel_update", "キャンセル", show=True),
        Binding("q", "quit_app", "終了", show=True),
    ]

    DEFAULT_CSS = """
    UpdateModal {
        align: center middle;
    }
    #update-box {
        width: 56;
        height: auto;
        background: $surface;
        border: thick $warning;
        padding: 1 2;
    }
    #update-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: $warning;
    }
    LoadingIndicator {
        height: 3;
        color: $warning;
    }
    #update-status {
        text-align: center;
        color: $text-muted;
        height: 1;
    }
    #update-hint {
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Container(
            Label("🔄  リポジトリを更新中...", id="update-title"),
            LoadingIndicator(),
            Label("", id="update-status"),
            Label("[Esc] キャンセル    [q] 終了", id="update-hint"),
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
                capture_output=True,
                text=True,
                timeout=30,
            )
            if worker.is_cancelled:
                return
            if result.returncode == 0:
                msg = result.stdout.strip() or "最新の状態です"
                self.app.call_from_thread(self._on_done, True, msg)
            else:
                err = result.stderr.strip() or "不明なエラー"
                self.app.call_from_thread(self._on_done, False, err)
        except subprocess.TimeoutExpired:
            if not worker.is_cancelled:
                self.app.call_from_thread(self._on_done, False, "タイムアウト (30秒)")
        except Exception as e:
            if not worker.is_cancelled:
                self.app.call_from_thread(self._on_done, False, str(e))

    def _on_done(self, success: bool, message: str) -> None:
        _write_last_update()
        self.query_one("#update-status", Label).update(
            f"✓  {message}" if success else f"✗  {message}"
        )
        self.query_one("#update-hint", Label).update("[Esc] 続ける    [q] 終了")
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


# ── タスク追加モーダル ────────────────────────────────────────────────────────

class AddTaskModal(ModalScreen):
    """タスク追加モーダル"""

    DEFAULT_CSS = """
    AddTaskModal {
        align: center middle;
    }
    #dialog {
        width: 68;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #dialog-title {
        text-style: bold;
        margin-bottom: 1;
    }
    .field-label {
        color: $text-muted;
        margin-top: 1;
    }
    #dialog-hint {
        color: $text-muted;
        margin-top: 1;
        text-align: right;
    }
    #dialog Input {
        width: 100%;
    }
    """

    def __init__(self, project_id: str, section_id: str | None, location: str) -> None:
        super().__init__()
        self.project_id = project_id
        self.section_id = section_id
        self.location = location

    def compose(self) -> ComposeResult:
        hint = f" → {self.location}" if self.location else ""
        yield Container(
            Label(f"タスクを追加{hint}", id="dialog-title"),
            Label("タスク名 *", classes="field-label"),
            Input(placeholder="タスク名を入力...", id="input-name"),
            Label("説明 (任意)", classes="field-label"),
            Input(placeholder="説明を入力...", id="input-desc"),
            Label("Tab で移動  /  Enter で追加  /  Esc で閉じる", id="dialog-hint"),
            id="dialog",
        )

    def on_mount(self) -> None:
        self.query_one("#input-name", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        # どちらのフィールドから Enter を押しても即追加
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
            self.dismiss(None)


# ── タスク詳細・編集モーダル ──────────────────────────────────────────────────

class TaskDetailModal(ModalScreen):
    """タスク詳細の表示と編集モーダル"""

    DEFAULT_CSS = """
    TaskDetailModal {
        align: center middle;
    }
    #detail-dialog {
        width: 68;
        height: auto;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #detail-title {
        text-style: bold;
        margin-bottom: 1;
    }
    .field-label {
        color: $text-muted;
        margin-top: 1;
    }
    #detail-hint {
        color: $text-muted;
        margin-top: 1;
        text-align: right;
    }
    #detail-dialog Input {
        width: 100%;
    }
    """

    def __init__(self, task_id: str, content: str) -> None:
        super().__init__()
        self._task_id = task_id
        self._initial_content = content
        self._initial_desc: str | None = None

    def compose(self) -> ComposeResult:
        yield Container(
            Label("タスクを編集", id="detail-title"),
            Label("タスク名 *", classes="field-label"),
            Input(value=self._initial_content, id="detail-input-name"),
            Label("説明", classes="field-label"),
            Input(placeholder="説明を入力...", id="detail-input-desc"),
            Label("Tab で移動  /  Enter で保存  /  Esc でキャンセル", id="detail-hint"),
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
            self.dismiss(None)


# ── メインアプリ ──────────────────────────────────────────────────────────────

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
    #jump-input {
        display: none;
        height: 3;
        border: tall $accent;
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "終了"),
        Binding("a", "add_task", "タスク追加"),
        Binding("space", "complete_task", "タスク完了", show=True, priority=True),
        Binding("r", "refresh", "更新"),
        Binding("g", "goto_line", "行ジャンプ", show=False),
        Binding("u", "undo", "元に戻す", show=False),
        Binding("ctrl+r", "redo", "やり直し", show=False),
        Binding("ctrl+w", "collapse_others", "他を折りたたむ", show=False),
    ]

    def __init__(self, needs_update: bool = False) -> None:
        super().__init__()
        self.needs_update = needs_update
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self._jump_originals: list[tuple] = []  # [(node, original_label), ...]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield TaskTree("プロジェクト", id="tree")
        yield Static("読み込み中...", id="status")
        yield Input(
            placeholder="行番号を入力  [Enter] ジャンプ  [Esc] キャンセル",
            id="jump-input",
        )
        yield Footer()

    def on_mount(self) -> None:
        if self.needs_update:
            self.push_screen(UpdateModal(), self._after_update)
        else:
            self._load_projects()

    def _after_update(self, _result) -> None:
        self._load_projects()

    # ── プロジェクト読み込み ──────────────────────────────────────────────────

    def _load_projects(self) -> None:
        tree = self.query_one("#tree", Tree)
        tree.clear()
        tree.root.expand()
        self._set_status("読み込み中...")
        try:
            projects = api_get_projects()
        except Exception as e:
            self._set_status(f"エラー: {e}")
            return

        for project in projects:
            node = tree.root.add(
                Text(f"📋 {project['name']}"),
                data={"type": "project", "id": project["id"], "name": project["name"]},
                expand=False,
            )
            node.add_leaf(
                Text("  読み込み中...", style="dim"),
                data={"type": "loading"},
            )
        self._set_status(
            "プロジェクトを選択して展開  |  [a] 追加  [space] 完了  [Enter] 詳細  [r] 更新  [q] 終了"
        )

    # ── ノード展開イベント ────────────────────────────────────────────────────

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        node = event.node
        data = node.data
        if not data or data["type"] != "project":
            return
        children = list(node.children)
        if children and children[0].data and children[0].data.get("type") != "loading":
            return
        self._load_project_content(node, data["id"])

    def _load_project_content(self, project_node, project_id: str) -> None:
        project_node.remove_children()
        try:
            sections = api_get_sections(project_id)
            tasks = api_get_tasks(project_id)
        except Exception as e:
            project_node.add_leaf(
                Text(f"  エラー: {e}", style="red bold"),
                data={"type": "error"},
            )
            return
        self._build_tree_content(project_node, project_id, sections, tasks)

    def _build_tree_content(self, project_node, project_id: str, sections: list, tasks: list) -> None:
        no_section_tasks = [t for t in tasks if not t.get("section_id") and t.get("section_id") != 0]
        if no_section_tasks:
            ns_node = project_node.add(
                Text("  （セクションなし）", style="dim"),
                data={"type": "section", "id": None, "name": "", "project_id": project_id},
                expand=True,
            )
            for task in no_section_tasks:
                ns_node.add_leaf(
                    Text(f"    ○ {task['content']}"),
                    data={"type": "task", "id": task["id"], "content": task["content"],
                          "project_id": project_id, "section_id": None},
                )

        for section in sections:
            section_tasks = [t for t in tasks if str(t.get("section_id", "")) == str(section["id"])]
            label = Text(f"  📁 {section['name']}")
            if section_tasks:
                label.append(f"  {len(section_tasks)}", style="dim")
            sec_node = project_node.add(
                label,
                data={"type": "section", "id": section["id"], "name": section["name"],
                      "project_id": project_id},
                expand=True,
            )
            for task in section_tasks:
                sec_node.add_leaf(
                    Text(f"    ○ {task['content']}"),
                    data={"type": "task", "id": task["id"], "content": task["content"],
                          "project_id": project_id, "section_id": section["id"]},
                )

        if not sections and not tasks:
            project_node.add_leaf(
                Text("  タスクなし", style="dim"),
                data={"type": "empty"},
            )

    # ── ノード選択イベント ────────────────────────────────────────────────────

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        data = event.node.data
        if not data:
            return
        match data["type"]:
            case "project":
                self._set_status(f"📋 {data['name']}  |  [a] タスク追加  [r] 更新  [ctrl+w] 他を折りたたむ")
            case "section":
                name = data["name"] or "セクションなし"
                self._set_status(f"📁 {name}  |  [a] タスク追加  [r] 更新")
            case "task":
                self._set_status(
                    f"○ {data['content']}  |  [Enter] 詳細/編集  [space] 完了  [a] タスク追加"
                )
            case _:
                self._set_status("")

    # ── アクション ────────────────────────────────────────────────────────────

    def on_task_tree_open_task(self, event: TaskTree.OpenTask) -> None:
        """TaskTree からの Enter イベント（タスクノード選択時のみ発火）"""
        task_data = event.node_data

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
                api_update_task(task_id, new_content, new_desc)
            except Exception as e:
                self._set_status(f"エラー: {e}")
                return
            self._undo_stack.append({
                "description": f"タスク更新: {old_content}",
                "undo_fn": lambda: api_update_task(task_id, old_content, old_desc),
                "redo_fn": lambda: api_update_task(task_id, new_content, new_desc),
                "project_id": project_id,
            })
            self._redo_stack.clear()
            self._refresh_project()

        self.push_screen(
            TaskDetailModal(task_data["id"], task_data["content"]),
            on_detail_dismiss,
        )

    def action_add_task(self) -> None:
        project_id, section_id, location = self._get_context()
        if not project_id:
            self._set_status("タスクを追加する場所を選択してください")
            return

        def on_dismiss(result: tuple[str, str | None] | None) -> None:
            if not result:
                return
            content, description = result
            try:
                task = api_add_task(content, project_id, section_id, description)
            except Exception as e:
                self._set_status(f"エラー: {e}")
                return
            task_id = task["id"]
            self._undo_stack.append({
                "description": f"タスク追加: {content}",
                "undo_fn": lambda: api_delete_task(task_id),
                "redo_fn": lambda: api_add_task(content, project_id, section_id, description),
                "project_id": project_id,
            })
            self._redo_stack.clear()
            self._refresh_project_by_id(project_id)

        self.push_screen(AddTaskModal(project_id, section_id, location), on_dismiss)

    def action_complete_task(self) -> None:
        tree = self.query_one("#tree", Tree)
        node = tree.cursor_node
        if not node or not node.data or node.data["type"] != "task":
            self._set_status("完了にするタスクを選択してください")
            return
        task_id = node.data["id"]
        content = node.data["content"]
        project_id = node.data["project_id"]
        try:
            api_close_task(task_id)
        except Exception as e:
            self._set_status(f"エラー: {e}")
            return
        self._undo_stack.append({
            "description": f"タスク完了: {content}",
            "undo_fn": lambda: api_reopen_task(task_id),
            "redo_fn": lambda: api_close_task(task_id),
            "project_id": project_id,
        })
        self._redo_stack.clear()
        self._refresh_project_by_id(project_id)

    def action_refresh(self) -> None:
        project_node = self._get_project_node()
        if project_node:
            status = self.query_one("#status", Static)
            status.add_class("refreshing")
            self._set_status("🔄 更新中...")
            self._refresh_worker(project_node, project_node.data["id"])
        else:
            self._load_projects()

    @work(thread=True)
    def _refresh_worker(self, project_node, project_id: str) -> None:
        try:
            sections = api_get_sections(project_id)
            tasks = api_get_tasks(project_id)
            self.call_from_thread(self._apply_refresh, project_node, project_id, sections, tasks, None)
        except Exception as e:
            self.call_from_thread(self._apply_refresh, project_node, project_id, None, None, str(e))

    def _apply_refresh(
        self,
        project_node,
        project_id: str,
        sections: list | None,
        tasks: list | None,
        error: str | None,
    ) -> None:
        status = self.query_one("#status", Static)
        status.remove_class("refreshing")
        project_node.remove_children()
        if error:
            project_node.add_leaf(Text(f"  エラー: {error}", style="red bold"), data={"type": "error"})
            self._set_status(f"エラー: {error}")
            return
        self._build_tree_content(project_node, project_id, sections or [], tasks or [])
        self._set_status(
            "プロジェクトを選択して展開  |  [a] 追加  [space] 完了  [Enter] 詳細  [r] 更新  [q] 終了"
        )

    def action_undo(self) -> None:
        if not self._undo_stack:
            self._set_status("元に戻す操作がありません")
            return
        entry = self._undo_stack.pop()
        try:
            entry["undo_fn"]()
        except Exception as e:
            self._set_status(f"元に戻す失敗: {e}")
            return
        self._redo_stack.append(entry)
        self._set_status(f"元に戻しました: {entry['description']}")
        self._refresh_project_by_id(entry["project_id"])

    def action_redo(self) -> None:
        if not self._redo_stack:
            self._set_status("やり直す操作がありません")
            return
        entry = self._redo_stack.pop()
        try:
            entry["redo_fn"]()
        except Exception as e:
            self._set_status(f"やり直し失敗: {e}")
            return
        self._undo_stack.append(entry)
        self._set_status(f"やり直しました: {entry['description']}")
        self._refresh_project_by_id(entry["project_id"])

    def action_collapse_others(self) -> None:
        """現在いるセクション以外の兄弟セクションを折りたたむ"""
        # カーソルからセクションノードを辿る
        tree = self.query_one("#tree", Tree)
        node = tree.cursor_node
        if not node:
            self._set_status("セクションが選択されていません")
            return
        current = node
        while current and current.data and current.data.get("type") != "section":
            current = current.parent
        if not current or not current.data or current.data.get("type") != "section":
            self._set_status("セクションが選択されていません")
            return
        section_node = current
        project_node = section_node.parent
        if not project_node:
            return
        for child in project_node.children:
            if child is not section_node:
                child.collapse()

    # ── ヘルパー ─────────────────────────────────────────────────────────────

    def _set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

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
                return data["project_id"], data["id"], data["name"] or "セクションなし"
            case "task":
                return data["project_id"], data.get("section_id"), ""
            case _:
                return None, None, ""

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
            Text("  読み込み中...", style="dim"),
            data={"type": "loading"},
        )
        self._load_project_content(project_node, project_node.data["id"])

    def _refresh_project(self) -> None:
        project_node = self._get_project_node()
        if project_node:
            self._force_reload(project_node)

    def _refresh_project_by_id(self, project_id: str) -> None:
        """undo/redo 後、カーソル位置に関係なく対象プロジェクトを更新"""
        tree = self.query_one("#tree", Tree)
        for child in tree.root.children:
            if child.data and child.data.get("id") == project_id:
                self._force_reload(child)
                return
        self._refresh_project()

    # ── 行ジャンプ ────────────────────────────────────────────────────────────

    def _get_visible_nodes(self) -> list:
        """展開済みの全可視ノード（loading/error/empty を除く）を表示順で返す"""
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

    def action_goto_line(self) -> None:
        """g キー: 行番号を各ノードに表示してジャンプ入力を開く"""
        nodes = self._get_visible_nodes()
        if not nodes:
            return
        self._jump_originals = []
        for i, node in enumerate(nodes, start=1):
            self._jump_originals.append((node, node.label))
            original = node.label
            num = Text(f"{i:>3}│", style="cyan bold")
            if isinstance(original, Text):
                new_label = Text.assemble(num, original)
            else:
                new_label = Text.assemble(num, Text(str(original)))
            node.set_label(new_label)

        jump_input = self.query_one("#jump-input", Input)
        jump_input.display = True
        jump_input.value = ""
        jump_input.focus()

    def _exit_jump_mode(self, line_num: int | None) -> None:
        """ラベルを元に戻し、指定行があればカーソルを移動する"""
        nodes_in_order = [node for node, _ in self._jump_originals]
        for node, original_label in self._jump_originals:
            node.set_label(original_label)
        self._jump_originals = []

        jump_input = self.query_one("#jump-input", Input)
        jump_input.display = False

        tree = self.query_one("#tree", Tree)
        tree.focus()

        if line_num is not None and 1 <= line_num <= len(nodes_in_order):
            target = nodes_in_order[line_num - 1]
            tree.move_cursor(target)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "jump-input":
            return
        try:
            line_num = int(event.value.strip())
        except ValueError:
            line_num = None
        self._exit_jump_mode(line_num)

    def on_key(self, event) -> None:
        jump_input = self.query_one("#jump-input", Input)
        if jump_input.display and event.key == "escape":
            event.prevent_default()
            self._exit_jump_mode(None)


# ── エントリポイント ──────────────────────────────────────────────────────────

def run_tui() -> None:
    needs_update = _needs_update()
    TodoistApp(needs_update=needs_update).run()
