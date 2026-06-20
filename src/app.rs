use crate::api::ApiClient;
use crate::types::*;
use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};
use std::collections::HashMap;
use tokio::sync::mpsc::UnboundedSender;

pub struct App {
    pub projects_data: Vec<ProjectNode>,
    pub flat_nodes: Vec<FlatNode>,
    pub list_index: usize,
    pub mode: Mode,
    pub screen: Screen,
    pub status: String,
    pub colon_input: String,
    pub undo_stack: Vec<UndoEntry>,
    pub redo_stack: Vec<UndoEntry>,
    pub next_temp_id: u64,
    pub refreshing: bool,
    pub should_quit: bool,
    move_source: Option<(usize, usize, usize)>,
    api: ApiClient,
    tx: UnboundedSender<Message>,
}

impl App {
    pub fn new(token: String, tx: UnboundedSender<Message>) -> Self {
        Self {
            projects_data: Vec::new(),
            flat_nodes: Vec::new(),
            list_index: 0,
            mode: Mode::Normal,
            screen: Screen::Main,
            status: "Loading...".to_string(),
            colon_input: String::new(),
            undo_stack: Vec::new(),
            redo_stack: Vec::new(),
            next_temp_id: 0,
            refreshing: false,
            should_quit: false,
            move_source: None,
            api: ApiClient::new(token),
            tx,
        }
    }

    // ── Startup ───────────────────────────────────────────────────────────────

    pub fn load_projects(&mut self) {
        self.status = "Loading...".to_string();
        let api = self.api.clone();
        let tx = self.tx.clone();
        tokio::spawn(async move {
            match api.get_projects().await {
                Ok(p) => { let _ = tx.send(Message::ProjectsLoaded(p)); }
                Err(e) => { let _ = tx.send(Message::ProjectsLoadFailed(e)); }
            }
        });
    }

    // ── Flat list rebuild ─────────────────────────────────────────────────────

    pub fn rebuild_flat_nodes(&mut self) {
        let old_idx = self.list_index;
        self.flat_nodes.clear();

        for (pi, proj) in self.projects_data.iter().enumerate() {
            self.flat_nodes.push(FlatNode::Project(pi));
            if !proj.expanded { continue; }
            if !proj.loaded {
                self.flat_nodes.push(FlatNode::Loading(pi));
                continue;
            }
            for (si, sec) in proj.sections.iter().enumerate() {
                self.flat_nodes.push(FlatNode::Section(pi, si));
                if !sec.expanded { continue; }
                for (ti, _) in sec.tasks.iter().enumerate() {
                    self.flat_nodes.push(FlatNode::Task(pi, si, ti));
                }
            }
        }

        if self.flat_nodes.is_empty() {
            self.list_index = 0;
        } else if old_idx >= self.flat_nodes.len() {
            self.list_index = self.flat_nodes.len() - 1;
        }
    }

    pub fn current_flat_node(&self) -> Option<&FlatNode> {
        self.flat_nodes.get(self.list_index)
    }

    // ── Mode management ───────────────────────────────────────────────────────

    pub fn enter_normal_mode(&mut self) {
        self.mode = Mode::Normal;
        self.colon_input.clear();
    }

    pub fn enter_command_mode(&mut self) {
        self.mode = Mode::Command;
        self.status = "[a] Add  [Space] Complete  [r] Refresh  [e] Edit  [:] Command  [Esc] Cancel"
            .to_string();
    }

    pub fn enter_colon_mode(&mut self) {
        self.mode = Mode::Colon;
        self.colon_input.clear();
    }

    pub fn restore_default_status(&mut self) {
        self.status =
            "Expand a project  |  [Esc] command mode  |  j/k navigate  |  [q] quit".to_string();
    }

    // ── Paste (IME 確定テキスト) ──────────────────────────────────────────────

    pub fn on_paste(&mut self, text: &str) {
        match &mut self.screen {
            Screen::AddTask { name_input, desc_input, focused, .. } => {
                let input = if *focused == 0 { name_input } else { desc_input };
                for c in text.chars() {
                    input.on_char(c);
                }
            }
            Screen::EditTask { name_input, desc_input, focused, .. } => {
                let input = if *focused == 0 { name_input } else { desc_input };
                for c in text.chars() {
                    input.on_char(c);
                }
            }
            Screen::Main => {}
        }
    }

    // ── Key handling (main screen) ────────────────────────────────────────────

    pub fn on_key(&mut self, key: KeyEvent) {
        match &self.screen {
            Screen::AddTask { .. } => { self.on_key_add_task(key); return; }
            Screen::EditTask { .. } => { self.on_key_edit_task(key); return; }
            Screen::Main => {}
        }

        // Colon input captures all keys
        if self.mode == Mode::Colon {
            match key.code {
                KeyCode::Esc => {
                    self.enter_normal_mode();
                    self.restore_default_status();
                }
                KeyCode::Enter => {
                    let cmd = std::mem::take(&mut self.colon_input);
                    self.handle_colon_command(&cmd);
                }
                KeyCode::Backspace => { self.colon_input.pop(); }
                KeyCode::Char(c) => { self.colon_input.push(c); }
                _ => {}
            }
            return;
        }

        // j/k work in all modes
        match key.code {
            KeyCode::Char('j') => {
                if self.list_index + 1 < self.flat_nodes.len() {
                    self.list_index += 1;
                    self.update_status_for_cursor();
                }
                return;
            }
            KeyCode::Char('k') => {
                if self.list_index > 0 {
                    self.list_index -= 1;
                    self.update_status_for_cursor();
                }
                return;
            }
            _ => {}
        }

        match self.mode {
            Mode::Normal => match key.code {
                KeyCode::Esc => self.enter_command_mode(),
                KeyCode::Enter => self.on_enter(),
                KeyCode::Char('q') => self.should_quit = true,
                KeyCode::Char('u') => self.action_undo(),
                KeyCode::Char('r') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                    self.action_redo()
                }
                KeyCode::Char('w') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                    self.action_collapse_others()
                }
                _ => {}
            },
            Mode::Command => match key.code {
                KeyCode::Esc => {
                    self.enter_normal_mode();
                    self.restore_default_status();
                }
                KeyCode::Char(' ') => {
                    self.enter_normal_mode();
                    self.do_complete_task();
                }
                KeyCode::Char('a') => {
                    self.enter_normal_mode();
                    self.open_add_task_modal();
                }
                KeyCode::Char('r') => {
                    self.enter_normal_mode();
                    self.action_refresh();
                }
                KeyCode::Char('e') => {
                    self.enter_normal_mode();
                    self.open_edit_task_modal();
                }
                KeyCode::Char(':') => self.enter_colon_mode(),
                _ => {
                    self.enter_normal_mode();
                    self.restore_default_status();
                }
            },
            Mode::Move => match key.code {
                KeyCode::Esc => self.cancel_move(),
                KeyCode::Enter => self.execute_move(),
                _ => {}
            },
            Mode::Colon => {} // handled above
        }
    }

    fn on_enter(&mut self) {
        let node = match self.current_flat_node() {
            Some(n) => n.clone(),
            None => return,
        };
        match node {
            FlatNode::Project(pi) => self.toggle_project(pi),
            FlatNode::Section(pi, si) => {
                self.projects_data[pi].sections[si].expanded =
                    !self.projects_data[pi].sections[si].expanded;
                self.rebuild_flat_nodes();
            }
            FlatNode::Task(..) => {
                if self.mode == Mode::Move {
                    self.execute_move();
                }
            }
            FlatNode::Loading(_) => {}
        }
    }

    fn update_status_for_cursor(&mut self) {
        if self.mode != Mode::Normal { return; }
        let node = match self.current_flat_node() {
            Some(n) => n.clone(),
            None => return,
        };
        match node {
            FlatNode::Project(pi) => {
                let name = self.projects_data[pi].name.clone();
                self.status = format!(
                    "📋 {}  |  [Esc] command mode  [r] refresh  [ctrl+w] collapse", name
                );
            }
            FlatNode::Section(pi, si) => {
                let name = self.projects_data[pi].sections[si].name.clone();
                let label = if name.is_empty() { "No Section".to_string() } else { name };
                self.status = format!("📁 {}  |  [Esc] command mode", label);
            }
            FlatNode::Task(pi, si, ti) => {
                let content = self.projects_data[pi].sections[si].tasks[ti].content.clone();
                self.status = format!(
                    "○ {}  |  [Esc→e] edit  [Esc→Space] complete  [Esc→:mv] move", content
                );
            }
            FlatNode::Loading(_) => self.restore_default_status(),
        }
    }

    // ── Project expand / collapse ─────────────────────────────────────────────

    fn toggle_project(&mut self, pi: usize) {
        if self.projects_data[pi].expanded {
            self.projects_data[pi].expanded = false;
            self.rebuild_flat_nodes();
        } else {
            self.projects_data[pi].expanded = true;
            if !self.projects_data[pi].loaded {
                self.rebuild_flat_nodes();
                self.load_project_content(pi);
            } else {
                self.rebuild_flat_nodes();
            }
        }
    }

    fn load_project_content(&mut self, pi: usize) {
        let project_id = self.projects_data[pi].id.clone();
        let api = self.api.clone();
        let tx = self.tx.clone();
        tokio::spawn(async move {
            let sections = api.get_sections(&project_id).await;
            let tasks = api.get_tasks(&project_id).await;
            match (sections, tasks) {
                (Ok(s), Ok(t)) => {
                    let _ = tx.send(Message::ProjectContentLoaded {
                        project_id, sections: s, tasks: t,
                    });
                }
                (Err(e), _) | (_, Err(e)) => {
                    let _ = tx.send(Message::ProjectContentFailed { project_id, error: e });
                }
            }
        });
    }

    fn populate_project(&mut self, pi: usize, sections: Vec<crate::types::ApiSection>, tasks: Vec<crate::types::ApiTask>) {
        let project_id = self.projects_data[pi].id.clone();
        let mut result_sections: Vec<SectionNode> = Vec::new();

        let no_section_tasks: Vec<_> = tasks.iter()
            .filter(|t| t.section_id.is_none())
            .collect();
        if !no_section_tasks.is_empty() {
            result_sections.push(SectionNode {
                id: None,
                name: String::new(),
                project_id: project_id.clone(),
                expanded: true,
                tasks: no_section_tasks.iter().map(|t| TaskNode {
                    id: Some(t.id.clone()),
                    content: t.content.clone(),
                    project_id: project_id.clone(),
                    section_id: None,
                    order: t.order.unwrap_or(0),
                    pending: false,
                    moving: false,
                    temp_id: None,
                }).collect(),
            });
        }

        for sec in &sections {
            let section_tasks: Vec<_> = tasks.iter()
                .filter(|t| t.section_id.as_deref() == Some(sec.id.as_str()))
                .collect();
            result_sections.push(SectionNode {
                id: Some(sec.id.clone()),
                name: sec.name.clone(),
                project_id: project_id.clone(),
                expanded: true,
                tasks: section_tasks.iter().map(|t| TaskNode {
                    id: Some(t.id.clone()),
                    content: t.content.clone(),
                    project_id: project_id.clone(),
                    section_id: Some(sec.id.clone()),
                    order: t.order.unwrap_or(0),
                    pending: false,
                    moving: false,
                    temp_id: None,
                }).collect(),
            });
        }

        self.projects_data[pi].sections = result_sections;
        self.projects_data[pi].loaded = true;
    }

    fn refresh_project_by_id(&mut self, project_id: &str) {
        let pi = self.projects_data.iter().position(|p| p.id == project_id);
        if let Some(pi) = pi {
            if self.projects_data[pi].expanded {
                self.projects_data[pi].loaded = false;
                self.projects_data[pi].sections.clear();
                self.rebuild_flat_nodes();
                self.load_project_content(pi);
            } else {
                self.rebuild_flat_nodes();
            }
        } else {
            self.rebuild_flat_nodes();
        }
    }

    // ── Task operations ───────────────────────────────────────────────────────

    fn open_add_task_modal(&mut self) {
        let (project_id, section_id, location) = self.get_context();
        let Some(project_id) = project_id else {
            self.status = "Select a location to add a task".to_string();
            return;
        };
        self.screen = Screen::AddTask {
            project_id,
            section_id,
            location,
            name_input: TextInput::default(),
            desc_input: TextInput::default(),
            focused: 0,
        };
    }

    fn open_edit_task_modal(&mut self) {
        let node = match self.current_flat_node() {
            Some(FlatNode::Task(pi, si, ti)) => {
                let t = &self.projects_data[*pi].sections[*si].tasks[*ti];
                if t.pending { return; }
                (
                    t.id.clone().unwrap_or_default(),
                    t.content.clone(),
                    t.project_id.clone(),
                )
            }
            _ => {
                self.status = "Select a task to edit".to_string();
                return;
            }
        };
        let (task_id, content, project_id) = node;
        let api = self.api.clone();
        let tx = self.tx.clone();
        let tid = task_id.clone();
        tokio::spawn(async move {
            if let Ok(detail) = api.get_task(&tid).await {
                let _ = tx.send(Message::TaskDescriptionLoaded {
                    task_id: tid,
                    description: detail.description.unwrap_or_default(),
                });
            }
        });
        self.screen = Screen::EditTask {
            task_id,
            project_id,
            original_content: content.clone(),
            original_desc: None,
            name_input: TextInput::new(&content),
            desc_input: TextInput::default(),
            focused: 0,
            desc_loaded: false,
        };
    }

    fn do_complete_task(&mut self) {
        let (pi, si, ti) = match self.current_flat_node() {
            Some(FlatNode::Task(pi, si, ti)) => (*pi, *si, *ti),
            _ => {
                self.status = "Select a task to complete".to_string();
                return;
            }
        };
        let task = &mut self.projects_data[pi].sections[si].tasks[ti];
        if task.pending { return; }
        let task_id = task.id.clone().unwrap_or_default();
        let content = task.content.clone();
        let project_id = task.project_id.clone();
        task.pending = true;
        self.rebuild_flat_nodes();

        let api = self.api.clone();
        let tx = self.tx.clone();
        tokio::spawn(async move {
            match api.close_task(&task_id).await {
                Ok(()) => { let _ = tx.send(Message::TaskCompleted { task_id, content, project_id }); }
                Err(e) => { let _ = tx.send(Message::TaskCompleteFailed { task_id, error: e }); }
            }
        });
    }

    // ── Move mode ─────────────────────────────────────────────────────────────

    fn start_move(&mut self) {
        let (pi, si, ti) = match self.current_flat_node() {
            Some(FlatNode::Task(pi, si, ti)) => (*pi, *si, *ti),
            _ => {
                self.status = "Select a task to move".to_string();
                return;
            }
        };
        if self.projects_data[pi].sections[si].tasks[ti].pending { return; }
        let content = self.projects_data[pi].sections[si].tasks[ti].content.clone();
        self.move_source = Some((pi, si, ti));
        self.projects_data[pi].sections[si].tasks[ti].moving = true;
        self.mode = Mode::Move;
        self.rebuild_flat_nodes();
        self.status = format!(
            "Moving: {}  |  navigate to destination → [Enter]  [Esc] cancel", content
        );
    }

    fn cancel_move(&mut self) {
        if let Some((pi, si, ti)) = self.move_source.take() {
            self.projects_data[pi].sections[si].tasks[ti].moving = false;
        }
        self.enter_normal_mode();
        self.rebuild_flat_nodes();
        self.restore_default_status();
    }

    fn execute_move(&mut self) {
        let (src_pi, src_si, src_ti) = match self.move_source {
            Some(v) => v,
            None => { self.cancel_move(); return; }
        };
        let dest = match self.current_flat_node() {
            Some(FlatNode::Task(pi, si, ti)) => (*pi, *si, *ti),
            _ => {
                self.status = "Select a task as the destination".to_string();
                return;
            }
        };
        let (dest_pi, dest_si, _dest_ti) = dest;
        if src_pi == dest_pi && src_si == dest_si && src_ti == _dest_ti {
            self.cancel_move();
            return;
        }

        let dest_section_id = self.projects_data[dest_pi].sections[dest_si].id.clone();
        let dest_project_id = self.projects_data[dest_pi].id.clone();
        let src_project_id = self.projects_data[src_pi].id.clone();
        let task = &mut self.projects_data[src_pi].sections[src_si].tasks[src_ti];
        let task_id = task.id.clone().unwrap_or_default();
        task.moving = false;
        task.pending = true;

        self.move_source = None;
        self.enter_normal_mode();
        self.rebuild_flat_nodes();
        self.status = format!("Moving...");

        let api = self.api.clone();
        let tx = self.tx.clone();
        tokio::spawn(async move {
            let result = api.move_task(
                &task_id,
                dest_section_id.as_deref(),
                Some(dest_project_id.as_str()),
            ).await;
            match result {
                Ok(()) => {
                    let _ = tx.send(Message::TaskMoved {
                        task_id,
                        orig_project_id: src_project_id,
                        dest_project_id,
                    });
                }
                Err(e) => { let _ = tx.send(Message::TaskMoveFailed { task_id, error: e }); }
            }
        });
    }

    // ── Refresh ───────────────────────────────────────────────────────────────

    pub fn action_refresh(&mut self) {
        let expanded_ids: Vec<String> = self.projects_data.iter()
            .filter(|p| p.expanded)
            .map(|p| p.id.clone())
            .collect();
        self.refreshing = true;
        self.status = "🔄 Refreshing...".to_string();
        let api = self.api.clone();
        let tx = self.tx.clone();
        tokio::spawn(async move {
            let projects = match api.get_projects().await {
                Ok(p) => p,
                Err(e) => { let _ = tx.send(Message::FullRefreshFailed(e)); return; }
            };
            let mut expanded_data = HashMap::new();
            for pid in &expanded_ids {
                let s = api.get_sections(pid).await;
                let t = api.get_tasks(pid).await;
                if let (Ok(s), Ok(t)) = (s, t) {
                    expanded_data.insert(pid.clone(), (s, t));
                }
            }
            let _ = tx.send(Message::FullRefreshDone { projects, expanded_data });
        });
    }

    // ── Undo / Redo ───────────────────────────────────────────────────────────

    fn action_undo(&mut self) {
        let entry = match self.undo_stack.pop() {
            Some(e) => e,
            None => { self.status = "Nothing to undo".to_string(); return; }
        };
        let project_id = entry.project_id.clone();
        let desc = entry.description.clone();
        let api = self.api.clone();
        let tx = self.tx.clone();
        let op = entry.undo_op.clone();
        self.redo_stack.push(entry);
        self.status = format!("Undoing: {}", desc);
        self.dispatch_undo_op(op, project_id, api, tx);
    }

    fn action_redo(&mut self) {
        let entry = match self.redo_stack.pop() {
            Some(e) => e,
            None => { self.status = "Nothing to redo".to_string(); return; }
        };
        let project_id = entry.project_id.clone();
        let desc = entry.description.clone();
        let api = self.api.clone();
        let tx = self.tx.clone();
        let op = entry.redo_op.clone();
        self.undo_stack.push(entry);
        self.status = format!("Redoing: {}", desc);
        self.dispatch_undo_op(op, project_id, api, tx);
    }

    fn dispatch_undo_op(
        &self, op: UndoAction, project_id: String,
        api: ApiClient, tx: UnboundedSender<Message>,
    ) {
        tokio::spawn(async move {
            let result = match &op {
                UndoAction::DeleteTask { task_id } => api.delete_task(task_id).await,
                UndoAction::ReopenTask { task_id } => api.reopen_task(task_id).await,
                UndoAction::CloseTask { task_id } => api.close_task(task_id).await,
                UndoAction::AddTask { content, project_id, section_id, description } => {
                    api.add_task(content, project_id, section_id.as_deref(), description.as_deref())
                        .await
                        .map(|_| ())
                }
                UndoAction::UpdateTask { task_id, content, description } => {
                    api.update_task(task_id, content, description.as_deref())
                        .await
                        .map(|_| ())
                }
            };
            if let Err(e) = result {
                let _ = tx.send(Message::ProjectContentFailed { project_id, error: e });
            } else {
                let _ = tx.send(Message::ProjectContentLoaded {
                    project_id,
                    sections: vec![],
                    tasks: vec![],
                });
            }
        });
    }

    // ── Collapse others ───────────────────────────────────────────────────────

    fn action_collapse_others(&mut self) {
        let cur_sec = match self.current_flat_node() {
            Some(FlatNode::Section(pi, si)) => (*pi, *si),
            Some(FlatNode::Task(pi, si, _)) => (*pi, *si),
            _ => {
                self.status = "No section selected".to_string();
                return;
            }
        };
        let (cur_pi, cur_si) = cur_sec;
        for (si, sec) in self.projects_data[cur_pi].sections.iter_mut().enumerate() {
            if si != cur_si {
                sec.expanded = false;
            }
        }
        self.rebuild_flat_nodes();
    }

    // ── Colon command ─────────────────────────────────────────────────────────

    fn handle_colon_command(&mut self, cmd: &str) {
        self.enter_normal_mode();
        if cmd.is_empty() { self.restore_default_status(); return; }
        if cmd.ends_with('g') {
            if let Ok(n) = cmd[..cmd.len() - 1].parse::<usize>() {
                self.jump_to_line(n);
            } else {
                self.status = format!("Invalid command: {}", cmd);
            }
            return;
        }
        if cmd == "mv" { self.start_move(); return; }
        self.status = format!("Unknown command: :{}", cmd);
    }

    fn jump_to_line(&mut self, line_num: usize) {
        let total = self.flat_nodes.len();
        if line_num >= 1 && line_num <= total {
            self.list_index = line_num - 1;
        } else {
            self.status = format!("Line {} out of range (1–{})", line_num, total);
        }
    }

    // ── Modal key handling ────────────────────────────────────────────────────

    fn on_key_add_task(&mut self, key: KeyEvent) {
        let screen = match &mut self.screen {
            Screen::AddTask { name_input, desc_input, focused, .. } => {
                (name_input as *mut TextInput, desc_input as *mut TextInput, focused as *mut usize)
            }
            _ => return,
        };
        let (name_ptr, desc_ptr, focused_ptr) = screen;
        let (name_input, desc_input, focused) = unsafe {
            (&mut *name_ptr, &mut *desc_ptr, &mut *focused_ptr)
        };

        match key.code {
            KeyCode::Esc => { self.screen = Screen::Main; }
            KeyCode::Tab => { *focused = if *focused == 0 { 1 } else { 0 }; }
            KeyCode::BackTab => { *focused = if *focused == 0 { 1 } else { 0 }; }
            KeyCode::Enter => { self.submit_add_task(); }
            code => {
                let input = if *focused == 0 { name_input } else { desc_input };
                apply_key_to_input(input, code);
            }
        }
    }

    fn submit_add_task(&mut self) {
        let (project_id, section_id, content, description) = match &self.screen {
            Screen::AddTask { project_id, section_id, name_input, desc_input, .. } => {
                let content = name_input.value.trim().to_string();
                if content.is_empty() { return; }
                let desc = desc_input.value.trim().to_string();
                (
                    project_id.clone(),
                    section_id.clone(),
                    content,
                    if desc.is_empty() { None } else { Some(desc) },
                )
            }
            _ => return,
        };
        self.screen = Screen::Main;

        // Optimistic insert
        let temp_id = self.next_temp_id;
        self.next_temp_id += 1;
        let task_node = TaskNode {
            id: None,
            content: content.clone(),
            project_id: project_id.clone(),
            section_id: section_id.clone(),
            order: 0,
            pending: true,
            moving: false,
            temp_id: Some(temp_id),
        };
        let sec_idx = self.find_section_idx(&project_id, &section_id);
        if let Some((pi, si)) = sec_idx {
            self.projects_data[pi].sections[si].tasks.push(task_node);
            self.rebuild_flat_nodes();
        }

        let api = self.api.clone();
        let tx = self.tx.clone();
        let pid = project_id.clone();
        let sid = section_id.clone();
        let c = content.clone();
        let d = description.clone();
        tokio::spawn(async move {
            match api.add_task(&c, &pid, sid.as_deref(), d.as_deref()).await {
                Ok(task) => {
                    let _ = tx.send(Message::TaskAdded {
                        temp_id, task,
                        content: c, description: d, project_id: pid, section_id: sid,
                    });
                }
                Err(e) => { let _ = tx.send(Message::TaskAddFailed { temp_id, error: e }); }
            }
        });
    }

    fn on_key_edit_task(&mut self, key: KeyEvent) {
        let screen = match &mut self.screen {
            Screen::EditTask { name_input, desc_input, focused, .. } => {
                (name_input as *mut TextInput, desc_input as *mut TextInput, focused as *mut usize)
            }
            _ => return,
        };
        let (name_ptr, desc_ptr, focused_ptr) = screen;
        let (name_input, desc_input, focused) = unsafe {
            (&mut *name_ptr, &mut *desc_ptr, &mut *focused_ptr)
        };

        match key.code {
            KeyCode::Esc => { self.screen = Screen::Main; }
            KeyCode::Tab => { *focused = if *focused == 0 { 1 } else { 0 }; }
            KeyCode::BackTab => { *focused = if *focused == 0 { 1 } else { 0 }; }
            KeyCode::Enter => { self.submit_edit_task(); }
            code => {
                let input = if *focused == 0 { name_input } else { desc_input };
                apply_key_to_input(input, code);
            }
        }
    }

    fn submit_edit_task(&mut self) {
        let (task_id, project_id, new_content, new_desc, old_content, old_desc) =
            match &self.screen {
                Screen::EditTask {
                    task_id, project_id, name_input, desc_input,
                    original_content, original_desc, ..
                } => {
                    let content = name_input.value.trim().to_string();
                    if content.is_empty() { return; }
                    let desc = desc_input.value.trim().to_string();
                    (
                        task_id.clone(),
                        project_id.clone(),
                        content,
                        if desc.is_empty() { None } else { Some(desc) },
                        original_content.clone(),
                        original_desc.clone(),
                    )
                }
                _ => return,
            };
        self.screen = Screen::Main;

        // Optimistic update
        if let Some(task) = self.find_task_mut(&task_id) {
            task.content = new_content.clone();
            task.pending = true;
        }
        self.rebuild_flat_nodes();

        let api = self.api.clone();
        let tx = self.tx.clone();
        let tid = task_id.clone();
        let nc = new_content.clone();
        let nd = new_desc.clone();
        let oc = old_content.clone();
        let od = old_desc.clone();
        let pid = project_id.clone();
        tokio::spawn(async move {
            match api.update_task(&tid, &nc, nd.as_deref()).await {
                Ok(_) => {
                    let _ = tx.send(Message::TaskEdited {
                        task_id: tid, new_content: nc, new_desc: nd,
                        old_content: oc, old_desc: od, project_id: pid,
                    });
                }
                Err(e) => {
                    let _ = tx.send(Message::TaskEditFailed {
                        task_id: tid, old_content: oc, error: e,
                    });
                }
            }
        });
    }

    // ── Message handling ──────────────────────────────────────────────────────

    pub fn handle_message(&mut self, msg: Message) {
        match msg {
            Message::ProjectsLoaded(projects) => {
                self.projects_data = projects.into_iter().map(|p| ProjectNode {
                    id: p.id, name: p.name, expanded: false, loaded: false, sections: vec![],
                }).collect();
                self.rebuild_flat_nodes();
                self.restore_default_status();
            }
            Message::ProjectsLoadFailed(e) => {
                self.status = format!("Error: {}", e);
            }
            Message::ProjectContentLoaded { project_id, sections, tasks } => {
                // If this is a undo/redo refresh signal (empty sections/tasks), just reload
                if sections.is_empty() && tasks.is_empty() {
                    self.refresh_project_by_id(&project_id);
                    return;
                }
                let pi = self.projects_data.iter().position(|p| p.id == project_id);
                if let Some(pi) = pi {
                    self.populate_project(pi, sections, tasks);
                    self.rebuild_flat_nodes();
                    self.restore_default_status();
                }
            }
            Message::ProjectContentFailed { project_id, error } => {
                let pi = self.projects_data.iter().position(|p| p.id == project_id);
                if let Some(pi) = pi {
                    self.projects_data[pi].loaded = true;
                }
                self.rebuild_flat_nodes();
                self.status = format!("Error: {}", error);
            }
            Message::TaskAdded { temp_id, task, content, description, project_id, section_id } => {
                let task_id = task.id.clone();
                if let Some(t) = self.find_pending_task_mut(temp_id) {
                    t.id = Some(task_id.clone());
                    t.pending = false;
                    t.order = task.order.unwrap_or(0);
                }
                self.rebuild_flat_nodes();
                self.undo_stack.push(UndoEntry {
                    description: format!("Add task: {}", content),
                    project_id: project_id.clone(),
                    undo_op: UndoAction::DeleteTask { task_id: task_id.clone() },
                    redo_op: UndoAction::AddTask { content, project_id, section_id, description },
                });
                self.redo_stack.clear();
            }
            Message::TaskAddFailed { temp_id, error } => {
                self.remove_pending_task(temp_id);
                self.rebuild_flat_nodes();
                self.status = format!("Error: {}", error);
            }
            Message::TaskCompleted { task_id, content, project_id } => {
                self.remove_task_by_id(&task_id);
                self.rebuild_flat_nodes();
                self.undo_stack.push(UndoEntry {
                    description: format!("Complete task: {}", content),
                    project_id: project_id.clone(),
                    undo_op: UndoAction::ReopenTask { task_id: task_id.clone() },
                    redo_op: UndoAction::CloseTask { task_id },
                });
                self.redo_stack.clear();
            }
            Message::TaskCompleteFailed { task_id, error } => {
                if let Some(t) = self.find_task_mut(&task_id) { t.pending = false; }
                self.rebuild_flat_nodes();
                self.status = format!("Error: {}", error);
            }
            Message::TaskEdited { task_id, new_content, new_desc, old_content, old_desc, project_id } => {
                if let Some(t) = self.find_task_mut(&task_id) {
                    t.content = new_content.clone();
                    t.pending = false;
                }
                self.rebuild_flat_nodes();
                self.undo_stack.push(UndoEntry {
                    description: format!("Update task: {}", old_content),
                    project_id,
                    undo_op: UndoAction::UpdateTask {
                        task_id: task_id.clone(), content: old_content, description: old_desc,
                    },
                    redo_op: UndoAction::UpdateTask {
                        task_id, content: new_content, description: new_desc,
                    },
                });
                self.redo_stack.clear();
            }
            Message::TaskEditFailed { task_id, old_content, error } => {
                if let Some(t) = self.find_task_mut(&task_id) {
                    t.content = old_content;
                    t.pending = false;
                }
                self.rebuild_flat_nodes();
                self.status = format!("Error: {}", error);
            }
            Message::TaskMoved { task_id: _, orig_project_id, dest_project_id } => {
                self.refresh_project_by_id(&dest_project_id);
                if orig_project_id != dest_project_id {
                    self.refresh_project_by_id(&orig_project_id);
                }
            }
            Message::TaskMoveFailed { task_id, error } => {
                if let Some(t) = self.find_task_mut(&task_id) {
                    t.pending = false;
                    t.moving = false;
                }
                self.rebuild_flat_nodes();
                self.status = format!("Move failed: {}", error);
            }
            Message::FullRefreshDone { projects, expanded_data } => {
                self.refreshing = false;
                self.projects_data = projects.into_iter().map(|p| {
                    let mut node = ProjectNode {
                        id: p.id.clone(), name: p.name,
                        expanded: false, loaded: false, sections: vec![],
                    };
                    if let Some((sections, tasks)) = expanded_data.get(&p.id) {
                        node.expanded = true;
                        let pi_tmp = 0; // We'll populate inline
                        let _ = pi_tmp;
                        let project_id = node.id.clone();
                        let mut result_sections: Vec<SectionNode> = Vec::new();
                        let no_sec: Vec<_> = tasks.iter().filter(|t| t.section_id.is_none()).collect();
                        if !no_sec.is_empty() {
                            result_sections.push(SectionNode {
                                id: None, name: String::new(),
                                project_id: project_id.clone(), expanded: true,
                                tasks: no_sec.iter().map(|t| TaskNode {
                                    id: Some(t.id.clone()), content: t.content.clone(),
                                    project_id: project_id.clone(), section_id: None,
                                    order: t.order.unwrap_or(0), pending: false, moving: false, temp_id: None,
                                }).collect(),
                            });
                        }
                        for sec in sections {
                            let stasks: Vec<_> = tasks.iter()
                                .filter(|t| t.section_id.as_deref() == Some(sec.id.as_str()))
                                .collect();
                            result_sections.push(SectionNode {
                                id: Some(sec.id.clone()), name: sec.name.clone(),
                                project_id: project_id.clone(), expanded: true,
                                tasks: stasks.iter().map(|t| TaskNode {
                                    id: Some(t.id.clone()), content: t.content.clone(),
                                    project_id: project_id.clone(),
                                    section_id: Some(sec.id.clone()),
                                    order: t.order.unwrap_or(0), pending: false, moving: false, temp_id: None,
                                }).collect(),
                            });
                        }
                        node.sections = result_sections;
                        node.loaded = true;
                    }
                    node
                }).collect();
                self.rebuild_flat_nodes();
                self.restore_default_status();
            }
            Message::FullRefreshFailed(e) => {
                self.refreshing = false;
                self.status = format!("Error: {}", e);
            }
            Message::TaskDescriptionLoaded { task_id, description } => {
                if let Screen::EditTask { task_id: tid, desc_input, original_desc, desc_loaded, .. } =
                    &mut self.screen
                {
                    if *tid == task_id {
                        desc_input.value = description.clone();
                        desc_input.cursor = description.len();
                        *original_desc = if description.is_empty() { None } else { Some(description) };
                        *desc_loaded = true;
                    }
                }
            }
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    fn get_context(&self) -> (Option<String>, Option<String>, String) {
        match self.current_flat_node() {
            Some(FlatNode::Project(pi)) => {
                let p = &self.projects_data[*pi];
                (Some(p.id.clone()), None, p.name.clone())
            }
            Some(FlatNode::Section(pi, si)) => {
                let s = &self.projects_data[*pi].sections[*si];
                let name = if s.name.is_empty() { "No Section".to_string() } else { s.name.clone() };
                (Some(s.project_id.clone()), s.id.clone(), name)
            }
            Some(FlatNode::Task(pi, si, _)) => {
                let s = &self.projects_data[*pi].sections[*si];
                (Some(s.project_id.clone()), s.id.clone(), String::new())
            }
            _ => (None, None, String::new()),
        }
    }

    fn find_section_idx(&self, project_id: &str, section_id: &Option<String>) -> Option<(usize, usize)> {
        for (pi, proj) in self.projects_data.iter().enumerate() {
            if proj.id != project_id { continue; }
            for (si, sec) in proj.sections.iter().enumerate() {
                let matches = match (section_id, &sec.id) {
                    (None, None) => true,
                    (Some(a), Some(b)) => a == b,
                    _ => false,
                };
                if matches { return Some((pi, si)); }
            }
        }
        None
    }

    fn find_task_mut(&mut self, task_id: &str) -> Option<&mut TaskNode> {
        for proj in &mut self.projects_data {
            for sec in &mut proj.sections {
                for task in &mut sec.tasks {
                    if task.id.as_deref() == Some(task_id) { return Some(task); }
                }
            }
        }
        None
    }

    fn find_pending_task_mut(&mut self, temp_id: u64) -> Option<&mut TaskNode> {
        for proj in &mut self.projects_data {
            for sec in &mut proj.sections {
                for task in &mut sec.tasks {
                    if task.temp_id == Some(temp_id) { return Some(task); }
                }
            }
        }
        None
    }

    fn remove_task_by_id(&mut self, task_id: &str) {
        for proj in &mut self.projects_data {
            for sec in &mut proj.sections {
                sec.tasks.retain(|t| t.id.as_deref() != Some(task_id));
            }
        }
    }

    fn remove_pending_task(&mut self, temp_id: u64) {
        for proj in &mut self.projects_data {
            for sec in &mut proj.sections {
                sec.tasks.retain(|t| t.temp_id != Some(temp_id));
            }
        }
    }
}

fn apply_key_to_input(input: &mut TextInput, code: KeyCode) {
    match code {
        KeyCode::Char(c) => input.on_char(c),
        KeyCode::Backspace => input.on_backspace(),
        KeyCode::Delete => input.on_delete(),
        KeyCode::Left => input.move_left(),
        KeyCode::Right => input.move_right(),
        KeyCode::Home => input.move_home(),
        KeyCode::End => input.move_end(),
        _ => {}
    }
}
