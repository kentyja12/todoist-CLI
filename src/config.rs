use std::io::{BufRead, Write};
use std::path::PathBuf;

pub fn config_dir() -> PathBuf {
    #[cfg(target_os = "windows")]
    {
        let base = std::env::var("APPDATA")
            .map(PathBuf::from)
            .unwrap_or_else(|_| dirs::home_dir().unwrap_or_else(|| PathBuf::from(".")));
        base.join("todash")
    }
    #[cfg(not(target_os = "windows"))]
    {
        let base = std::env::var("XDG_CONFIG_HOME")
            .map(PathBuf::from)
            .unwrap_or_else(|_| {
                dirs::home_dir()
                    .unwrap_or_else(|| PathBuf::from("."))
                    .join(".config")
            });
        base.join("todash")
    }
}

pub fn config_file() -> PathBuf {
    config_dir().join(".env")
}

pub fn is_configured() -> bool {
    let cf = config_file();
    if !cf.exists() {
        return false;
    }
    if let Ok(file) = std::fs::File::open(&cf) {
        for line in std::io::BufReader::new(file).lines().flatten() {
            if let Some(token) = line.strip_prefix("TODOIST_TOKEN=") {
                return !token.trim().is_empty();
            }
        }
    }
    false
}

pub fn load_config() -> (Option<String>, u64) {
    let mut token: Option<String> = None;
    let mut tty: u64 = 3600;
    if let Ok(file) = std::fs::File::open(config_file()) {
        for line in std::io::BufReader::new(file).lines().flatten() {
            if let Some(v) = line.strip_prefix("TODOIST_TOKEN=") {
                let v = v.trim().to_string();
                if !v.is_empty() {
                    token = Some(v);
                }
            } else if let Some(v) = line.strip_prefix("TTY=") {
                if let Ok(n) = v.trim().parse::<u64>() {
                    tty = n;
                }
            }
        }
    }
    (token, tty)
}

pub fn write_config(token: &str, tty: u64) -> std::io::Result<()> {
    std::fs::create_dir_all(config_dir())?;
    let mut file = std::fs::File::create(config_file())?;
    writeln!(file, "TODOIST_TOKEN={}", token)?;
    writeln!(file, "TTY={}", tty)?;
    Ok(())
}
