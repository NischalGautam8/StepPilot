// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/

mod capture;
mod cursor;
mod overlay;
mod sidecar;
mod ws_client;

use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    Emitter, Manager,
};
use tauri_plugin_global_shortcut::{Builder, Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        // Register the global shortcut plugin with a global event handler
        .plugin(
            Builder::new()
                .with_handler(move |app_handle, shortcut, event| {
                    let ctrl_alt_k = Shortcut::new(
                        Some(Modifiers::CONTROL | Modifiers::ALT),
                        Code::KeyK,
                    );
                    
                    if shortcut == &ctrl_alt_k && event.state() == ShortcutState::Pressed {
                        if let Some(window) = app_handle.get_webview_window("main") {
                            let is_visible = window.is_visible().unwrap_or(false);
                            if is_visible {
                                let _ = window.hide();
                            } else {
                                let _ = window.show();
                                let _ = window.set_focus();
                            }
                        }
                    }
                })
                .build()
        )
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            greet,
            capture::capture_screen,
            capture::capture_screen_diff,
            capture::reset_screenshot_diff,
            cursor::get_cursor_position,
            cursor::set_active_target_bbox,
            cursor::set_overlay_card_bounds,
            cursor::clear_overlay_card_bounds,
            overlay::toggle_overlay,
            overlay::set_overlay_ignore_cursor,
            sidecar::start_sidecar,
            sidecar::stop_sidecar,
            ws_client::ws_connect,
            ws_client::ws_send_screenshot,
            ws_client::ws_send_task_start
        ])
        .setup(|app| {
            // Configure overlay window for transparent click-through
            if let Some(overlay_window) = app.get_webview_window("overlay") {
                let _ = overlay_window.set_ignore_cursor_events(true);
            }

            // Spawn background thread to monitor cursor click coordinates and auto-advance
            let app_handle = app.handle().clone();
            std::thread::spawn(move || {
                let mut clicked = false;
                loop {
                    std::thread::sleep(std::time::Duration::from_millis(50));
                    
                    #[cfg(target_os = "windows")]
                    {
                        use tauri::Emitter;
                        
                        // FFI declarations
                        extern "system" {
                            fn GetAsyncKeyState(vKey: i32) -> i16;
                            fn GetCursorPos(lpPoint: *mut cursor::POINT) -> i32;
                        }
                        
                        let mut pt = cursor::POINT { x: 0, y: 0 };
                        let got_cursor = unsafe { GetCursorPos(&mut pt) != 0 };
                        
                        if got_cursor {
                            // Check if cursor is inside the floating overlay card bounds
                            let mut is_inside_card = false;
                            
                            if let Some(overlay_window) = app_handle.get_webview_window("overlay") {
                                // Get the native DPI scale factor to match physical and logical coordinates
                                let scale = overlay_window.scale_factor().unwrap_or(1.0);
                                
                                {
                                    let card_bounds_guard = cursor::OVERLAY_CARD_BOUNDS.lock().unwrap();
                                    if let Some((cx, cy, cw, ch)) = *card_bounds_guard {
                                        // Scale logical layout bounds up to physical screen pixels
                                        let cx_phys = (cx as f64 * scale) as i32;
                                        let cy_phys = (cy as f64 * scale) as i32;
                                        let cw_phys = (cw as f64 * scale) as i32;
                                        let ch_phys = (ch as f64 * scale) as i32;
                                        
                                        if pt.x >= cx_phys && pt.x <= (cx_phys + cw_phys) &&
                                           pt.y >= cy_phys && pt.y <= (cy_phys + ch_phys) {
                                            is_inside_card = true;
                                        }
                                    }
                                }
                                
                                // Dynamically toggle overlay click-through
                                let _ = overlay_window.set_ignore_cursor_events(!is_inside_card);
                            }
                            
                            // Left click down! Check if active bounding box is set
                            let key_state = unsafe { GetAsyncKeyState(0x01) }; // VK_LBUTTON
                            let is_down = key_state < 0;
                            
                            if is_down {
                                if !clicked {
                                    clicked = true;
                                    let bbox_guard = cursor::ACTIVE_TARGET_BBOX.lock().unwrap();
                                    if let Some((bx, by, bw, bh)) = *bbox_guard {
                                        // Check coordinates with generous 15px bounding box click padding!
                                        let padding = 15;
                                        if pt.x >= (bx - padding) && pt.x <= (bx + bw + padding) &&
                                           pt.y >= (by - padding) && pt.y <= (by + bh + padding) {
                                            println!("Auto-advancing: User clicked inside target bounding box [{}, {}]", pt.x, pt.y);
                                            let _ = app_handle.emit("auto-advance-step", ());
                                        }
                                    }
                                }
                            } else {
                                clicked = false;
                            }
                        }
                    }
                }
            });

            // Register global hotkey: Ctrl + Alt + K
            let ctrl_alt_k = Shortcut::new(
                Some(Modifiers::CONTROL | Modifiers::ALT),
                Code::KeyK,
            );
            
            if let Err(e) = app.global_shortcut().register(ctrl_alt_k) {
                eprintln!("Failed to register global hotkey Ctrl+Alt+K: {}", e);
            }

            // Create system tray menu items
            let start_i = MenuItem::with_id(app, "start", "Start", true, None::<&str>)?;
            let stop_i = MenuItem::with_id(app, "stop", "Stop", true, None::<&str>)?;
            let settings_i = MenuItem::with_id(app, "settings", "Settings", true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            
            let menu = Menu::with_items(app, &[&start_i, &stop_i, &settings_i, &quit_i])?;

            // Create system tray icon using the default window icon
            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .on_menu_event(|app_handle, event| {
                    match event.id.as_ref() {
                        "start" => {
                            println!("Tray: Start clicked");
                            let _ = app_handle.emit("tray-start", ());
                        }
                        "stop" => {
                            println!("Tray: Stop clicked");
                            let _ = app_handle.emit("tray-stop", ());
                        }
                        "settings" => {
                            println!("Tray: Settings clicked");
                            if let Some(window) = app_handle.get_webview_window("main") {
                                let _ = window.show();
                                let _ = window.set_focus();
                                let _ = app_handle.emit("navigate", "settings");
                            }
                        }
                        "quit" => {
                            println!("Tray: Quit clicked");
                            app_handle.exit(0);
                        }
                        _ => {}
                    }
                })
                .build(app)?;

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
