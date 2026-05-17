// Rust screen capture module (DXGI implementation in Sprint 2)

#[tauri::command]
pub fn capture_screen() -> Result<String, String> {
    println!("capture_screen called (placeholder)");
    Ok("Placeholder base64 image data".to_string())
}
