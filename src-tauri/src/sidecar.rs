// Rust sidecar manager module (spawns/manages FastAPI in production)

use std::sync::Mutex;
use tauri::AppHandle;

#[allow(dead_code)]
pub struct SidecarState {
    pub process: Mutex<Option<String>>,
}

#[tauri::command]
pub fn start_sidecar(_app: AppHandle) -> Result<String, String> {
    println!("start_sidecar called (placeholder for production sidecar)");
    Ok("Sidecar started successfully".to_string())
}

#[tauri::command]
pub fn stop_sidecar() -> Result<String, String> {
    println!("stop_sidecar called (placeholder for production sidecar)");
    Ok("Sidecar stopped successfully".to_string())
}
