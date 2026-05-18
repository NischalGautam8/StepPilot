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
            overlay::toggle_overlay,
            sidecar::start_sidecar,
            sidecar::stop_sidecar,
            ws_client::ws_connect,
            ws_client::ws_send_screenshot
        ])
        .setup(|app| {
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
