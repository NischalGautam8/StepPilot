// Rust overlay management module (transparent click-through overlay in Sprint 5)
use tauri::Manager;

#[tauri::command]
pub fn toggle_overlay(app: tauri::AppHandle, show: bool) -> Result<(), String> {
    println!("toggle_overlay called with: {}", show);
    if let Some(window) = app.get_webview_window("overlay") {
        if show {
            window.show().map_err(|e| e.to_string())?;
        } else {
            window.hide().map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}

#[tauri::command]
pub fn set_overlay_ignore_cursor(app: tauri::AppHandle, ignore: bool) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("overlay") {
        window.set_ignore_cursor_events(ignore).map_err(|e| e.to_string())?;
    }
    Ok(())
}
