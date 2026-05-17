// Rust overlay management module (transparent click-through overlay in Sprint 5)

#[tauri::command]
pub fn toggle_overlay(show: bool) -> Result<(), String> {
    println!("toggle_overlay called with: {}", show);
    Ok(())
}
