#![allow(dead_code)]
use serde::Deserialize;
use std::collections::HashMap;

// ── API response types ────────────────────────────────────────────────────────

#[derive(Debug, Clone, Deserialize)]
pub struct ApiProject {
    pub id: String,
    pub name: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ApiSection {
    pub id: String,
    pub name: String,
    pub project_id: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ApiTask {
    pub id: String,
    pub content: String,
    pub project_id: String,
    pub section_id: Option<String>,
    pub order: Option<i64>,
    pub description: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ApiTaskDetail {
    pub id: String,
    pub content: String,
    pub description: Option<String>,
}

// ── App tree types ────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct TaskNode {
    pub id: Option<String>,
    pub content: String,
    pub project_id: String,
    pub section_id: Option<String>,
    pub order: i64,
    pub pending: bool,
    pub moving: bool,
    pub temp_id: Option<u64>,
}

#[derive(Debug, Clone)]
pub struct SectionNode {
    pub id: Option<String>,
    pub name: String,
    pub project_id: String,
    pub expanded: bool,
    pub tasks: Vec<TaskNode>,
}

#[derive(Debug, Clone)]
pub struct ProjectNode {
    pub id: String,
    pub name: String,
    pub expanded: bool,
    pub loaded: bool,
    pub sections: Vec<SectionNode>,
}

// ── Flat list index ───────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub enum FlatNode {
    Project(usize),
    Section(usize, usize),
    Task(usize, usize, usize),
    Loading(usize),
}

// ── Mode / Screen ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub enum Mode {
    Normal,
    Command,
    Colon,
    Move,
}

#[derive(Debug)]
pub enum Screen {
    Main,
    AddTask {
        project_id: String,
        section_id: Option<String>,
        location: String,
        name_input: TextInput,
        desc_input: TextInput,
        focused: usize,
    },
    EditTask {
        task_id: String,
        project_id: String,
        original_content: String,
        original_desc: Option<String>,
        name_input: TextInput,
        desc_input: TextInput,
        focused: usize,
        desc_loaded: bool,
    },
}

// ── Text input widget ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, Default)]
pub struct TextInput {
    pub value: String,
    pub cursor: usize,
}

impl TextInput {
    pub fn new(initial: &str) -> Self {
        Self { cursor: initial.len(), value: initial.to_string() }
    }

    pub fn on_char(&mut self, c: char) {
        self.value.insert(self.cursor, c);
        self.cursor += c.len_utf8();
    }

    pub fn on_backspace(&mut self) {
        if self.cursor > 0 {
            let c_len = self.value[..self.cursor]
                .chars().last().map(|c| c.len_utf8()).unwrap_or(1);
            self.cursor -= c_len;
            self.value.remove(self.cursor);
        }
    }

    pub fn on_delete(&mut self) {
        if self.cursor < self.value.len() {
            self.value.remove(self.cursor);
        }
    }

    pub fn move_left(&mut self) {
        if self.cursor > 0 {
            let c_len = self.value[..self.cursor]
                .chars().last().map(|c| c.len_utf8()).unwrap_or(1);
            self.cursor -= c_len;
        }
    }

    pub fn move_right(&mut self) {
        if self.cursor < self.value.len() {
            let c = self.value[self.cursor..].chars().next().unwrap();
            self.cursor += c.len_utf8();
        }
    }

    pub fn move_home(&mut self) { self.cursor = 0; }
    pub fn move_end(&mut self) { self.cursor = self.value.len(); }

    pub fn char_count_before_cursor(&self) -> usize {
        self.value[..self.cursor].chars().count()
    }
}

// ── Undo / Redo ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub enum UndoAction {
    DeleteTask { task_id: String },
    ReopenTask { task_id: String },
    CloseTask { task_id: String },
    AddTask {
        content: String,
        project_id: String,
        section_id: Option<String>,
        description: Option<String>,
    },
    UpdateTask {
        task_id: String,
        content: String,
        description: Option<String>,
    },
}

#[derive(Debug, Clone)]
pub struct UndoEntry {
    pub description: String,
    pub project_id: String,
    pub undo_op: UndoAction,
    pub redo_op: UndoAction,
}

// ── Background messages ───────────────────────────────────────────────────────

#[derive(Debug)]
pub enum Message {
    ProjectsLoaded(Vec<ApiProject>),
    ProjectsLoadFailed(String),
    ProjectContentLoaded {
        project_id: String,
        sections: Vec<ApiSection>,
        tasks: Vec<ApiTask>,
    },
    ProjectContentFailed {
        project_id: String,
        error: String,
    },
    TaskAdded {
        temp_id: u64,
        task: ApiTask,
        content: String,
        description: Option<String>,
        project_id: String,
        section_id: Option<String>,
    },
    TaskAddFailed {
        temp_id: u64,
        error: String,
    },
    TaskCompleted {
        task_id: String,
        content: String,
        project_id: String,
    },
    TaskCompleteFailed {
        task_id: String,
        error: String,
    },
    TaskEdited {
        task_id: String,
        new_content: String,
        new_desc: Option<String>,
        old_content: String,
        old_desc: Option<String>,
        project_id: String,
    },
    TaskEditFailed {
        task_id: String,
        old_content: String,
        error: String,
    },
    TaskMoved {
        task_id: String,
        orig_project_id: String,
        dest_project_id: String,
    },
    TaskMoveFailed {
        task_id: String,
        error: String,
    },
    FullRefreshDone {
        projects: Vec<ApiProject>,
        expanded_data: HashMap<String, (Vec<ApiSection>, Vec<ApiTask>)>,
    },
    FullRefreshFailed(String),
    TaskDescriptionLoaded {
        task_id: String,
        description: String,
    },
}
