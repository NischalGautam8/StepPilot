// WebSocket client for communicating with Python FastAPI backend
use futures_util::{SinkExt, StreamExt};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::Mutex;
use tokio::time::{sleep, Duration};
use tokio_tungstenite::{connect_async, tungstenite::Message};

/// Message types for WebSocket communication protocol
#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum WsMessage {
    /// Screenshot data from Rust to Python
    Screenshot {
        data: String,  // base64 JPEG
        width: u32,
        height: u32,
        timestamp: u64,
    },
    /// User task query from frontend to Python
    TaskStart {
        query: String,
        timestamp: u64,
    },
    /// Guidance step from Python to frontend
    TaskStep {
        step_number: u32,
        total_steps: u32,
        instruction: String,
        target_element: Option<ElementInfo>,
    },
    /// Cursor position from Rust to Python
    CursorPos {
        x: i32,
        y: i32,
        timestamp: u64,
    },
    /// Error message
    Error {
        message: String,
        code: Option<String>,
    },
    /// Acknowledgement
    Ack {
        received: String,
    },
    /// Ping/Pong for health check
    Ping,
    Pong,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ElementInfo {
    pub id: String,
    pub element_type: String,
    pub text: String,
    pub bbox: BoundingBox,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct BoundingBox {
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub height: i32,
}

/// WebSocket client with reconnection logic
pub struct WsClient {
    url: String,
    sender: Arc<Mutex<Option<tokio_tungstenite::WebSocketStream<tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>>>>>,
    reconnect_attempts: Arc<Mutex<u32>>,
    max_reconnect_attempts: u32,
}

impl WsClient {
    pub fn new(url: String) -> Self {
        Self {
            url,
            sender: Arc::new(Mutex::new(None)),
            reconnect_attempts: Arc::new(Mutex::new(0)),
            max_reconnect_attempts: 10,
        }
    }

    /// Connect to WebSocket server with exponential backoff
    pub async fn connect(&self) -> Result<(), String> {
        let mut attempts = self.reconnect_attempts.lock().await;
        
        loop {
            match connect_async(&self.url).await {
                Ok((ws_stream, _)) => {
                    println!("WebSocket connected to {}", self.url);
                    *self.sender.lock().await = Some(ws_stream);
                    *attempts = 0;
                    return Ok(());
                }
                Err(e) => {
                    *attempts += 1;
                    if *attempts >= self.max_reconnect_attempts {
                        return Err(format!(
                            "Failed to connect after {} attempts: {}",
                            self.max_reconnect_attempts, e
                        ));
                    }
                    
                    // Exponential backoff: 1s, 2s, 4s, 8s, ...
                    let delay = Duration::from_secs(2u64.pow(*attempts - 1));
                    println!(
                        "WebSocket connection failed (attempt {}), retrying in {:?}...",
                        *attempts, delay
                    );
                    sleep(delay).await;
                }
            }
        }
    }

    /// Send a message to the WebSocket server
    pub async fn send(&self, message: WsMessage) -> Result<(), String> {
        let json = serde_json::to_string(&message)
            .map_err(|e| format!("Failed to serialize message: {}", e))?;
        
        let mut sender_guard = self.sender.lock().await;
        
        if let Some(ws_stream) = sender_guard.as_mut() {
            ws_stream
                .send(Message::Text(json))
                .await
                .map_err(|e| format!("Failed to send message: {}", e))?;
            Ok(())
        } else {
            Err("WebSocket not connected".to_string())
        }
    }

    /// Receive a message from the WebSocket server
    pub async fn receive(&self) -> Result<Option<WsMessage>, String> {
        let mut sender_guard = self.sender.lock().await;
        
        if let Some(ws_stream) = sender_guard.as_mut() {
            match ws_stream.next().await {
                Some(Ok(Message::Text(text))) => {
                    let message: WsMessage = serde_json::from_str(&text)
                        .map_err(|e| format!("Failed to deserialize message: {}", e))?;
                    Ok(Some(message))
                }
                Some(Ok(Message::Close(_))) => {
                    println!("WebSocket connection closed by server");
                    *sender_guard = None;
                    Err("Connection closed".to_string())
                }
                Some(Err(e)) => Err(format!("WebSocket error: {}", e)),
                None => Ok(None),
                _ => Ok(None),
            }
        } else {
            Err("WebSocket not connected".to_string())
        }
    }

    /// Check if connected
    pub async fn is_connected(&self) -> bool {
        self.sender.lock().await.is_some()
    }

    /// Disconnect
    pub async fn disconnect(&self) {
        let mut sender_guard = self.sender.lock().await;
        if let Some(mut ws_stream) = sender_guard.take() {
            let _ = ws_stream.close(None).await;
            println!("WebSocket disconnected");
        }
    }

    /// Start health check ping loop (call every 10 seconds)
    pub async fn start_health_check(&self) {
        let client = self.clone_for_task();
        tokio::spawn(async move {
            loop {
                sleep(Duration::from_secs(10)).await;
                if client.is_connected().await {
                    if let Err(e) = client.send(WsMessage::Ping).await {
                        println!("Health check ping failed: {}", e);
                        // Attempt reconnection
                        let _ = client.connect().await;
                    }
                }
            }
        });
    }

    /// Clone for use in async tasks
    fn clone_for_task(&self) -> Self {
        Self {
            url: self.url.clone(),
            sender: Arc::clone(&self.sender),
            reconnect_attempts: Arc::clone(&self.reconnect_attempts),
            max_reconnect_attempts: self.max_reconnect_attempts,
        }
    }
}

/// Tauri command to initialize WebSocket connection
#[tauri::command]
pub async fn ws_connect(url: String) -> Result<String, String> {
    let client = WsClient::new(url);
    client.connect().await?;
    Ok("Connected".to_string())
}

/// Tauri command to send screenshot via WebSocket
#[tauri::command]
pub async fn ws_send_screenshot(
    url: String,
    data: String,
    width: u32,
    height: u32,
) -> Result<(), String> {
    let client = WsClient::new(url);
    if !client.is_connected().await {
        client.connect().await?;
    }
    
    let timestamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_secs();
    
    client
        .send(WsMessage::Screenshot {
            data,
            width,
            height,
            timestamp,
        })
        .await
}
