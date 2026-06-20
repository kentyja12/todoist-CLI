use crate::app::App;
use crate::types::{FlatNode, Mode, Screen};
use chrono::Local;
use ratatui::{
    layout::{Constraint, Direction, Layout, Margin, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Clear, List, ListItem, ListState, Paragraph},
    Frame,
};

pub fn render(f: &mut Frame, app: &App) {
    let colon_height: u16 = if app.mode == Mode::Colon { 3 } else { 1 };
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(2),              // header
            Constraint::Fill(1),                // list
            Constraint::Length(1),              // status
            Constraint::Length(colon_height),   // mode / colon input
        ])
        .split(f.area());

    render_header(f, chunks[0]);
    render_list(f, chunks[1], app);
    render_status(f, chunks[2], app);
    render_mode_line(f, chunks[3], app);

    match &app.screen {
        Screen::AddTask { name_input, desc_input, focused, location, .. } => {
            render_add_modal(f, f.area(), name_input, desc_input, *focused, location);
        }
        Screen::EditTask { name_input, desc_input, focused, desc_loaded, .. } => {
            render_edit_modal(f, f.area(), name_input, desc_input, *focused, *desc_loaded);
        }
        Screen::Main => {}
    }
}

// ── Header ────────────────────────────────────────────────────────────────────

fn render_header(f: &mut Frame, area: Rect) {
    let time = Local::now().format("%H:%M:%S").to_string();
    let line = Line::from(vec![
        Span::styled(" Todash ", Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)),
        Span::styled(time, Style::default().fg(Color::DarkGray)),
    ]);
    let p = Paragraph::new(line)
        .block(Block::default().borders(Borders::BOTTOM));
    f.render_widget(p, area);
}

// ── Main list ─────────────────────────────────────────────────────────────────

fn render_list(f: &mut Frame, area: Rect, app: &App) {
    let items: Vec<ListItem> = app.flat_nodes.iter().enumerate().map(|(i, node)| {
        make_list_item(node, app, i + 1)
    }).collect();

    let list = List::new(items)
        .highlight_style(Style::default().bg(Color::DarkGray))
        .highlight_symbol("");

    let mut state = ListState::default();
    if !app.flat_nodes.is_empty() {
        state.select(Some(app.list_index));
    }

    f.render_stateful_widget(list, area, &mut state);
}

fn make_list_item(node: &FlatNode, app: &App, line_num: usize) -> ListItem<'static> {
    let num = Span::styled(
        format!("{:>3}│", line_num),
        Style::default().fg(Color::DarkGray),
    );

    let content: Span = match node {
        FlatNode::Project(pi) => {
            let proj = &app.projects_data[*pi];
            let icon = if proj.expanded { "▼ " } else { "▶ " };
            Span::styled(
                format!(" {}📋 {}", icon, proj.name),
                Style::default().add_modifier(Modifier::BOLD),
            )
        }
        FlatNode::Section(pi, si) => {
            let sec = &app.projects_data[*pi].sections[*si];
            let icon = if sec.expanded { "▼ " } else { "▶ " };
            let name = if sec.name.is_empty() { "No Section" } else { &sec.name };
            Span::raw(format!("   {}📁 {}", icon, name))
        }
        FlatNode::Task(pi, si, ti) => {
            let task = &app.projects_data[*pi].sections[*si].tasks[*ti];
            if task.moving {
                Span::styled(
                    format!("       ○ {}", task.content),
                    Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD),
                )
            } else if task.pending {
                Span::styled(
                    format!("       ○ {}", task.content),
                    Style::default().add_modifier(Modifier::DIM),
                )
            } else {
                Span::raw(format!("       ○ {}", task.content))
            }
        }
        FlatNode::Loading(_) => {
            Span::styled("      Loading...", Style::default().add_modifier(Modifier::DIM))
        }
    };

    ListItem::new(Line::from(vec![num, content]))
}

// ── Status bar ────────────────────────────────────────────────────────────────

fn render_status(f: &mut Frame, area: Rect, app: &App) {
    let style = if app.refreshing {
        Style::default().bg(Color::Yellow).fg(Color::Black)
    } else {
        Style::default().fg(Color::DarkGray)
    };
    let p = Paragraph::new(Span::styled(format!(" {}", app.status), style));
    f.render_widget(p, area);
}

// ── Mode indicator / colon input ──────────────────────────────────────────────

fn render_mode_line(f: &mut Frame, area: Rect, app: &App) {
    match app.mode {
        Mode::Normal => {
            let p = Paragraph::new(Span::styled(
                " NORMAL",
                Style::default().fg(Color::DarkGray),
            ));
            f.render_widget(p, area);
        }
        Mode::Command => {
            let p = Paragraph::new(Span::styled(
                " -- COMMAND --",
                Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD),
            ));
            f.render_widget(p, area);
        }
        Mode::Colon => {
            let input_line = format!(":{}", app.colon_input);
            let p = Paragraph::new(Span::styled(
                input_line.clone(),
                Style::default().fg(Color::Cyan),
            ))
            .block(Block::default().borders(Borders::TOP));
            f.render_widget(p, area);
            let cursor_x = area.x + 1 + app.colon_input.chars().count() as u16;
            let cursor_y = area.y + 1;
            f.set_cursor_position((cursor_x, cursor_y));
        }
        Mode::Move => {
            let p = Paragraph::new(Span::styled(
                " -- MOVE --",
                Style::default().fg(Color::Red).add_modifier(Modifier::BOLD),
            ));
            f.render_widget(p, area);
        }
    }
}

// ── Modals ────────────────────────────────────────────────────────────────────

fn render_add_modal(
    f: &mut Frame,
    area: Rect,
    name_input: &crate::types::TextInput,
    desc_input: &crate::types::TextInput,
    focused: usize,
    location: &str,
) {
    let modal_area = centered_rect(70, area);
    f.render_widget(Clear, modal_area);

    let title = if location.is_empty() {
        " Add Task ".to_string()
    } else {
        format!(" Add Task → {} ", location)
    };

    let block = Block::default()
        .title(title)
        .borders(Borders::ALL)
        .border_style(Style::default().fg(Color::Blue));
    f.render_widget(block, modal_area);

    let inner = modal_area.inner(Margin { horizontal: 1, vertical: 1 });
    render_two_field_form(f, inner, "Task Name *", name_input, "Description (optional)", desc_input, focused);
}

fn render_edit_modal(
    f: &mut Frame,
    area: Rect,
    name_input: &crate::types::TextInput,
    desc_input: &crate::types::TextInput,
    focused: usize,
    desc_loaded: bool,
) {
    let modal_area = centered_rect(70, area);
    f.render_widget(Clear, modal_area);

    let block = Block::default()
        .title(" Edit Task ")
        .borders(Borders::ALL)
        .border_style(Style::default().fg(Color::Green));
    f.render_widget(block, modal_area);

    let inner = modal_area.inner(Margin { horizontal: 1, vertical: 1 });
    let desc_label = if desc_loaded { "Description" } else { "Description (loading...)" };
    render_two_field_form(f, inner, "Task Name *", name_input, desc_label, desc_input, focused);
}

fn render_two_field_form(
    f: &mut Frame,
    area: Rect,
    label1: &str,
    input1: &crate::types::TextInput,
    label2: &str,
    input2: &crate::types::TextInput,
    focused: usize,
) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1),  // label 1
            Constraint::Length(1),  // input 1
            Constraint::Length(1),  // spacer
            Constraint::Length(1),  // label 2
            Constraint::Length(1),  // input 2
            Constraint::Fill(1),    // spacer
            Constraint::Length(1),  // hint
        ])
        .split(area);

    f.render_widget(
        Paragraph::new(Span::styled(label1, Style::default().fg(Color::DarkGray))),
        chunks[0],
    );
    render_text_input(f, chunks[1], input1, focused == 0);

    f.render_widget(
        Paragraph::new(Span::styled(label2, Style::default().fg(Color::DarkGray))),
        chunks[3],
    );
    render_text_input(f, chunks[4], input2, focused == 1);

    f.render_widget(
        Paragraph::new(Span::styled(
            "Tab: switch field  /  Enter: confirm  /  Esc: cancel",
            Style::default().fg(Color::DarkGray),
        )),
        chunks[6],
    );
}

fn render_text_input(
    f: &mut Frame,
    area: Rect,
    input: &crate::types::TextInput,
    focused: bool,
) {
    let style = if focused {
        Style::default().fg(Color::Yellow).add_modifier(Modifier::UNDERLINED)
    } else {
        Style::default().fg(Color::Gray)
    };
    // No block — a 1-row block with BOTTOM border would consume the only row for the border
    // leaving no space for the text itself.
    let p = Paragraph::new(Span::styled(input.value.clone(), style));
    f.render_widget(p, area);

    if focused {
        let char_offset = input.char_count_before_cursor() as u16;
        f.set_cursor_position((area.x + char_offset, area.y));
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

fn centered_rect(width_chars: u16, r: Rect) -> Rect {
    let height = 12u16;
    let x = r.x + r.width.saturating_sub(width_chars) / 2;
    let y = r.y + r.height.saturating_sub(height) / 2;
    Rect {
        x: x.min(r.x + r.width),
        y: y.min(r.y + r.height),
        width: width_chars.min(r.width),
        height: height.min(r.height),
    }
}
