// Rust sidecar manager module (spawns/manages FastAPI in production)

use std::sync::Mutex;
use tauri::{AppHandle, Manager};
use std::process::{Child, Command};
use std::path::PathBuf;
use std::sync::OnceLock;

static SIDECAR_CHILD: OnceLock<Mutex<Option<Child>>> = OnceLock::new();

fn get_sidecar_child() -> &'static Mutex<Option<Child>> {
    SIDECAR_CHILD.get_or_init(|| Mutex::new(None))
}

fn find_sidecar_path(app: &AppHandle) -> Option<PathBuf> {
    // 1. Try standard resolve using Resource base directory (appends target triple in bundling)
    if let Ok(resource_path) = app.path().resolve("binaries/backend-x86_64-pc-windows-msvc.exe", tauri::path::BaseDirectory::Resource) {
        if resource_path.exists() {
            return Some(resource_path);
        }
    }
    if let Ok(resource_path) = app.path().resolve("backend-x86_64-pc-windows-msvc.exe", tauri::path::BaseDirectory::Resource) {
        if resource_path.exists() {
            return Some(resource_path);
        }
    }

    // 2. Fall back to current executable's folder search
    if let Ok(current_exe) = std::env::current_exe() {
        if let Some(current_dir) = current_exe.parent() {
            let sidecar_path = current_dir.join("backend-x86_64-pc-windows-msvc.exe");
            if sidecar_path.exists() {
                return Some(sidecar_path);
            }
            let sidecar_path = current_dir.join("binaries").join("backend-x86_64-pc-windows-msvc.exe");
            if sidecar_path.exists() {
                return Some(sidecar_path);
            }
        }
    }

    None
}

#[tauri::command]
pub fn start_sidecar(app: AppHandle) -> Result<String, String> {
    println!("start_sidecar: checking for production sidecar binary...");
    
    // Check if sidecar is already running
    {
        let child_guard = get_sidecar_child().lock().unwrap();
        if child_guard.is_some() {
            return Ok("Sidecar is already running".to_string());
        }
    }

    if let Some(sidecar_path) = find_sidecar_path(&app) {
        println!("start_sidecar: found production sidecar at {:?}", sidecar_path);
        
        #[cfg(target_os = "windows")]
        {
            use std::os::windows::process::CommandExt;
            // CREATE_NO_WINDOW = 0x08000000 to hide console window of the spawned sidecar
            let mut cmd = Command::new(&sidecar_path);
            cmd.creation_flags(0x08000000);
            
            match cmd.spawn() {
                Ok(child) => {
                    let mut child_guard = get_sidecar_child().lock().unwrap();
                    *child_guard = Some(child);
                    Ok("Sidecar started successfully".to_string())
                }
                Err(e) => Err(format!("Failed to spawn sidecar: {}", e)),
            }
        }
        #[cfg(not(target_os = "windows"))]
        {
            match Command::new(&sidecar_path).spawn() {
                Ok(child) => {
                    let mut child_guard = get_sidecar_child().lock().unwrap();
                    *child_guard = Some(child);
                    Ok("Sidecar started successfully".to_string())
                }
                Err(e) => Err(format!("Failed to spawn sidecar: {}", e)),
            }
        }
    } else {
        println!("start_sidecar: production sidecar binary not found. Assuming development mode (Python backend is managed externally).");
        Ok("Sidecar running in dev mode (external)".to_string())
    }
}

#[tauri::command]
pub fn stop_sidecar() -> Result<String, String> {
    println!("stop_sidecar: stopping production sidecar...");
    let mut child_guard = get_sidecar_child().lock().unwrap();
    if let Some(mut child) = child_guard.take() {
        match child.kill() {
            Ok(_) => {
                let _ = child.wait(); // prevent zombie process
                Ok("Sidecar stopped successfully".to_string())
            }
            Err(e) => Err(format!("Failed to kill sidecar: {}", e)),
        }
    } else {
        Ok("No running sidecar to stop".to_string())
    }
}
