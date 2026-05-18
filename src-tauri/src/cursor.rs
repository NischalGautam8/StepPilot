// Rust cursor and click tracking module using raw Win32 APIs
use std::sync::Mutex;
use serde::{Serialize, Deserialize};

#[cfg(target_os = "windows")]
#[repr(C)]
pub struct POINT {
    pub x: i32,
    pub y: i32,
}

// Stores the active bounding box target to track left click event triggers
// Format: (x, y, width, height)
pub static ACTIVE_TARGET_BBOX: Mutex<Option<(i32, i32, i32, i32)>> = Mutex::new(None);

// Stores the floating overlay card bounds to dynamically toggle click-through
// Format: (x, y, width, height)
pub static OVERLAY_CARD_BOUNDS: Mutex<Option<(i32, i32, i32, i32)>> = Mutex::new(None);

#[cfg(target_os = "windows")]
extern "system" {
    fn GetCursorPos(lpPoint: *mut POINT) -> i32;
}

/// Retrieve the current cursor position coordinates
#[tauri::command]
pub fn get_cursor_position() -> Result<(i32, i32), String> {
    #[cfg(target_os = "windows")]
    {
        let mut pt = POINT { x: 0, y: 0 };
        unsafe {
            if GetCursorPos(&mut pt) != 0 {
                return Ok((pt.x, pt.y));
            }
        }
        Err("Failed to get cursor position".to_string())
    }
    #[cfg(not(target_os = "windows"))]
    {
        Ok((0, 0))
    }
}

/// Expose command to let React register the active coordinate bounding box target to monitor
#[tauri::command]
pub fn set_active_target_bbox(x: i32, y: i32, w: i32, h: i32) -> Result<(), String> {
    let mut bbox_guard = ACTIVE_TARGET_BBOX.lock().unwrap();
    if w <= 0 || h <= 0 {
        *bbox_guard = None;
        println!("Active target bounding box cleared in Rust core");
    } else {
        *bbox_guard = Some((x, y, w, h));
        println!("Active target bounding box registered in Rust core: [X={}, Y={}, W={}, H={}]", x, y, w, h);
    }
    Ok(())
}

/// Expose command to let React register the floating overlay card bounds
#[tauri::command]
pub fn set_overlay_card_bounds(x: i32, y: i32, w: i32, h: i32) -> Result<(), String> {
    let mut bounds = OVERLAY_CARD_BOUNDS.lock().unwrap();
    *bounds = Some((x, y, w, h));
    Ok(())
}

/// Expose command to clear overlay card bounds
#[tauri::command]
pub fn clear_overlay_card_bounds() -> Result<(), String> {
    let mut bounds = OVERLAY_CARD_BOUNDS.lock().unwrap();
    *bounds = None;
    Ok(())
}
