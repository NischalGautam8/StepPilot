// Rust cursor tracking module

#[tauri::command]
pub fn get_cursor_position() -> Result<(i32, i32), String> {
    println!("get_cursor_position called (placeholder)");
    Ok((0, 0))
}
