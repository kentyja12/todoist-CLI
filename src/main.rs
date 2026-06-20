mod api;
mod app;
mod config;
mod types;
mod ui;

use app::App;
use crossterm::{
    event::{self, Event, EnableBracketedPaste, DisableBracketedPaste},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{backend::CrosstermBackend, Terminal};
use std::{
    io::{self, Write},
    time::Duration,
};
use tokio::sync::mpsc;

// ── Setup wizard ──────────────────────────────────────────────────────────────

fn setup_wizard() -> io::Result<()> {
    println!();
    println!("╔══════════════════════════════════╗");
    println!("║        Welcome to Todash!        ║");
    println!("╚══════════════════════════════════╝");
    println!();
    println!("Get your API token from: https://app.todoist.com/app/settings/integrations/developer");
    println!();

    let token = loop {
        print!("Paste your Todoist API token: ");
        io::stdout().flush()?;
        let mut input = String::new();
        io::stdin().read_line(&mut input)?;
        let token = input.trim().to_string();
        if !token.is_empty() { break token; }
        println!("Token cannot be empty. Please try again.");
    };

    print!("Auto-refresh interval in seconds [3600]: ");
    io::stdout().flush()?;
    let mut tty_str = String::new();
    io::stdin().read_line(&mut tty_str)?;
    let tty: u64 = tty_str.trim().parse().unwrap_or(3600);

    config::write_config(&token, tty)?;
    println!();
    println!("Configuration saved. Launching Todash...");
    println!();

    Ok(())
}

// ── Main ──────────────────────────────────────────────────────────────────────

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    if !config::is_configured() {
        setup_wizard()?;
    }

    let (token, _tty) = config::load_config();
    let token = match token {
        Some(t) => t,
        None => {
            eprintln!("Error: TODOIST_TOKEN is not set in config.");
            std::process::exit(1);
        }
    };

    // Set up terminal
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen, EnableBracketedPaste)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let (tx, mut rx) = mpsc::unbounded_channel::<types::Message>();
    let mut app = App::new(token, tx);
    app.load_projects();

    let tick = Duration::from_millis(250);
    let result = run_loop(&mut terminal, &mut app, &mut rx, tick).await;

    // Restore terminal
    disable_raw_mode()?;
    execute!(terminal.backend_mut(), LeaveAlternateScreen, DisableBracketedPaste)?;
    terminal.show_cursor()?;

    result
}

async fn run_loop(
    terminal: &mut ratatui::Terminal<CrosstermBackend<io::Stdout>>,
    app: &mut App,
    rx: &mut mpsc::UnboundedReceiver<types::Message>,
    tick: Duration,
) -> anyhow::Result<()> {
    loop {
        // Drain background messages
        while let Ok(msg) = rx.try_recv() {
            app.handle_message(msg);
        }

        // Draw
        terminal.draw(|f| ui::render(f, app))?;

        if app.should_quit {
            break;
        }

        // Poll for terminal events
        if event::poll(tick)? {
            match event::read()? {
                Event::Key(key) => app.on_key(key),
                // IME で確定された文字列は Paste イベントとして届く
                Event::Paste(text) => app.on_paste(&text),
                _ => {}
            }
        }
    }
    Ok(())
}
