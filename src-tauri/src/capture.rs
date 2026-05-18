// Rust screen capture module using scrap crate (DXGI backend)
use base64::{engine::general_purpose, Engine as _};
use image::{ImageBuffer, ImageFormat, Rgba};
use scrap::{Capturer, Display};
use sha2::{Digest, Sha256};
use std::io::Cursor;
use std::sync::Mutex;
use std::time::Duration;

// Store last screenshot hash for differential detection
static LAST_SCREENSHOT_HASH: Mutex<Option<Vec<u8>>> = Mutex::new(None);

/// Capture screenshot from primary display and return as base64-encoded JPEG
#[tauri::command]
pub fn capture_screen() -> Result<String, String> {
    capture_screen_internal(false)
}

/// Capture screenshot with differential detection
/// Returns empty string if screenshot unchanged from last capture
#[tauri::command]
pub fn capture_screen_diff() -> Result<String, String> {
    capture_screen_internal(true)
}

fn capture_screen_internal(check_diff: bool) -> Result<String, String> {
    // Get primary display
    let display = Display::primary().map_err(|e| format!("Failed to get primary display: {}", e))?;
    
    let width = display.width();
    let height = display.height();
    
    // Create capturer
    let mut capturer = Capturer::new(display)
        .map_err(|e| format!("Failed to create capturer: {}", e))?;
    
    // Wait for frame (with timeout)
    let frame = loop {
        match capturer.frame() {
            Ok(frame) => break frame,
            Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                // Frame not ready yet, wait a bit
                std::thread::sleep(Duration::from_millis(10));
                continue;
            }
            Err(e) => return Err(format!("Failed to capture frame: {}", e)),
        }
    };
    
    // Convert BGRA to RGBA
    let mut rgba_data = Vec::with_capacity(frame.len());
    for chunk in frame.chunks_exact(4) {
        rgba_data.push(chunk[2]); // R
        rgba_data.push(chunk[1]); // G
        rgba_data.push(chunk[0]); // B
        rgba_data.push(chunk[3]); // A
    }
    
    // Create image buffer
    let img: ImageBuffer<Rgba<u8>, Vec<u8>> = ImageBuffer::from_raw(width as u32, height as u32, rgba_data)
        .ok_or_else(|| "Failed to create image buffer".to_string())?;
    
    // Differential detection: compute hash and compare
    if check_diff {
        let mut hasher = Sha256::new();
        hasher.update(img.as_raw());
        let current_hash = hasher.finalize().to_vec();
        
        let mut last_hash = LAST_SCREENSHOT_HASH.lock().unwrap();
        if let Some(ref prev_hash) = *last_hash {
            if prev_hash == &current_hash {
                // Screenshot unchanged, return empty string
                return Ok(String::new());
            }
        }
        *last_hash = Some(current_hash);
    }
    
    // Encode as JPEG with quality 75 for compression
    let mut jpeg_buffer = Cursor::new(Vec::new());
    img.write_to(&mut jpeg_buffer, ImageFormat::Jpeg)
        .map_err(|e| format!("Failed to encode JPEG: {}", e))?;
    
    // Convert to base64
    let base64_data = general_purpose::STANDARD.encode(jpeg_buffer.get_ref());
    
    Ok(base64_data)
}

/// Reset differential detection state (useful when starting new task)
#[tauri::command]
pub fn reset_screenshot_diff() {
    let mut last_hash = LAST_SCREENSHOT_HASH.lock().unwrap();
    *last_hash = None;
}
