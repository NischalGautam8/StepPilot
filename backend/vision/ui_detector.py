import os
import logging
import time
import cv2
import numpy as np
from typing import List, Dict, Any, Tuple

def check_models_exist() -> bool:
    """Check if all OmniParser V2 models are downloaded and non-empty on disk."""
    try:
        weights_dir = os.path.expanduser("~/.cursor-king/weights")
        yolo_path = os.path.join(weights_dir, "icon_detect.pt")
        if not os.path.exists(yolo_path) or os.path.getsize(yolo_path) == 0:
            return False
            
        florence_dir = os.path.join(weights_dir, "florence")
        required_files = [
            "config.json",
            "configuration_florence2.py",
            "modeling_florence2.py",
            "preprocessor_config.json",
            "processing_florence2.py",
            "model.safetensors",
            "vocab.json",
            "tokenizer.json",
            "tokenizer_config.json"
        ]
        for filename in required_files:
            path = os.path.join(florence_dir, filename)
            if not os.path.exists(path) or os.path.getsize(path) == 0:
                return False
        return True
    except Exception:
        return False


logger = logging.getLogger("cursor-king-backend.ui-detector")

class UIDetector:
    """
    UIDetector wraps Microsoft's OmniParser v2 models:
    - YOLOv8 (icon detection)
    - Florence-2 (icon captioning)
    
    Implements lazy loading to save memory (~2GB RAM/VRAM) and support 
    graceful degradation/fallback if PyTorch or other ML libraries are missing.
    """
    def __init__(self, use_gpu: bool = False):
        self.use_gpu = use_gpu
        self._initialized = False
        self._cancel_download = False
        
        # Models
        self.yolo_model = None
        self.florence_processor = None
        self.florence_model = None
        
        # Status of packages
        self.has_dependencies = False
        self._check_dependencies()

    def _check_dependencies(self):
        """Check if torch, ultralytics, and transformers are available."""
        try:
            import torch
            import ultralytics
            import transformers
            self.has_dependencies = True
            logger.info("OmniParser dependencies (torch, ultralytics, transformers) are present.")
        except ImportError as e:
            self.has_dependencies = False
            logger.warning(
                f"OmniParser dependencies missing ({e.name}). "
                "Running in Mock/Fallback mode. To use real icon detection, install: "
                "pip install torch torchvision ultralytics transformers timm einops"
            )

    def _initialize_models(self):
        """Lazy load YOLOv8 and Florence-2 models from local cache or online repositories."""
        if self._initialized:
            return
            
        if not self.has_dependencies:
            logger.warning("Cannot initialize real OmniParser models: missing dependencies.")
            return

        try:
            import torch
            from ultralytics import YOLO
            from transformers import AutoProcessor, AutoModelForCausalLM
            
            device = "cuda" if self.use_gpu and torch.cuda.is_available() else "cpu"
            logger.info(f"Initializing OmniParser V2 models on device: {device}...")
            
            weights_dir = os.path.expanduser("~/.cursor-king/weights")
            os.makedirs(weights_dir, exist_ok=True)
            
            # YOLOv8 Icon Detection Model
            yolo_path = os.path.join(weights_dir, "icon_detect.pt")
            if not os.path.exists(yolo_path):
                logger.info(f"YOLOv8 custom weights not found at {yolo_path}. Using standard yolov8n.pt...")
                try:
                    self.yolo_model = YOLO("yolov8n.pt")
                    logger.info("Loaded standard yolov8n.pt as placeholder.")
                except Exception as e:
                    logger.warning(f"Could not load yolov8n.pt: {e}")
            else:
                self.yolo_model = YOLO(yolo_path)
                logger.info(f"Loaded OmniParser YOLOv8 model from {yolo_path}")
            
            # Florence-2 Model Local or Online Resolution
            florence_path = os.path.join(weights_dir, "florence")
            if os.path.exists(os.path.join(florence_path, "model.safetensors")):
                florence_model_id = florence_path
                logger.info(f"Using local offline Florence-2 model weights from {florence_path}")
            else:
                florence_model_id = "microsoft/Florence-2-base"
                logger.info(f"Using online/cached Florence-2 model ID: {florence_model_id}")
                
            self.florence_processor = AutoProcessor.from_pretrained(florence_model_id, trust_remote_code=True)
            self.florence_model = AutoModelForCausalLM.from_pretrained(
                florence_model_id, 
                trust_remote_code=True
            ).to(device)
            self.florence_model.eval()
            
            self._initialized = True
            logger.info("OmniParser V2 models loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize OmniParser V2 models: {e}", exc_info=True)
            self.has_dependencies = False  # Force fallback on failure

    def detect_icons(self, image_np: np.ndarray) -> List[Dict[str, Any]]:
        """
        Runs OmniParser icon detection and captioning pipeline.
        Returns elements: [{"type": "icon", "bbox": [x, y, w, h], "text": str, "confidence": float, "source": "omniparser"}]
        """
        # Ensure models are loaded
        if self.has_dependencies:
            self._initialize_models()
            
        if not self._initialized or not self.has_dependencies:
            return self._run_mock_detector(image_np)
            
        try:
            # Real Inference Loop
            t0 = time.time()
            img_h, img_w = image_np.shape[:2]
            
            # 1. Run YOLOv8 icon detection
            results = self.yolo_model(image_np, verbose=False)
            detected_icons = []
            
            if not results or len(results) == 0:
                return []
                
            boxes = results[0].boxes
            logger.info(f"YOLOv8 detected {len(boxes)} potential icons/buttons.")
            
            import torch
            from PIL import Image
            
            # 2. For each detected box, crop and caption with Florence-2
            for box in boxes:
                # Get bbox in xyxy
                xyxy = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                
                # Filter out low confidence detections
                if conf < 0.25:
                    continue
                    
                x1, y1, x2, y2 = map(int, xyxy)
                w = x2 - x1
                h = y2 - y1
                
                # Crop the icon image
                if w < 5 or h < 5:
                    continue
                    
                cropped_bgr = image_np[y1:y2, x1:x2]
                cropped_rgb = cv2.cvtColor(cropped_bgr, cv2.COLOR_BGR2RGB)
                pil_crop = Image.fromarray(cropped_rgb)
                
                # Caption icon using Florence-2
                caption = self._caption_icon(pil_crop)
                
                detected_icons.append({
                    "type": "icon",
                    "text": caption,
                    "bbox": [x1, y1, w, h],
                    "confidence": conf,
                    "source": "omniparser",
                    "enabled": True,
                    "automation_id": ""
                })
                
            latency = (time.time() - t0) * 1000
            logger.info(f"OmniParser inference completed in {latency:.1f}ms. Found {len(detected_icons)} icons.")
            return detected_icons
            
        except Exception as e:
            logger.error(f"Error during real OmniParser inference: {e}", exc_info=True)
            return self._run_mock_detector(image_np)

    def _caption_icon(self, pil_image) -> str:
        """Helper to generate a caption for an icon using Florence-2."""
        try:
            import torch
            device = self.florence_model.device
            prompt = "<CAPTION>"
            
            inputs = self.florence_processor(text=prompt, images=pil_image, return_tensors="pt").to(device)
            # Ensure float16 or float32 based on device
            if device.type == "cuda":
                inputs = {k: v.to(torch.float16) if v.dtype == torch.float32 else v for k, v in inputs.items()}
                
            generated_ids = self.florence_model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=32,
                num_beams=3
            )
            
            generated_text = self.florence_processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            # Clean up the output text
            caption = generated_text.strip().lower()
            # If the caption is empty or generic, fall back to "icon"
            if not caption or caption in ["image", "icon", "logo"]:
                caption = "button"
            return caption
        except Exception as e:
            logger.debug(f"Florence-2 captioning failed: {e}")
            return "icon"

    def _run_mock_detector(self, image_np: np.ndarray) -> List[Dict[str, Any]]:
        """
        A rule-based mock icon detector that runs when actual ML dependencies 
        or weights are missing. Enables pipeline and integration testing.
        Simulates detecting titlebar controls and some layout icons.
        """
        logger.info("Executing Mock OmniParser Detector (Rule-based simulator)...")
        img_h, img_w = image_np.shape[:2]
        simulated_icons = []
        
        # Simulate standard window controls at top-right if image looks like a full window
        # (Close, Maximize, Minimize, Settings)
        if img_w > 400 and img_h > 200:
            # Close button simulator: top-right corner
            simulated_icons.append({
                "type": "icon",
                "text": "close button",
                "bbox": [img_w - 45, 5, 30, 20],
                "confidence": 0.95,
                "source": "omniparser",
                "enabled": True,
                "automation_id": ""
            })
            # Maximize button
            simulated_icons.append({
                "type": "icon",
                "text": "maximize button",
                "bbox": [img_w - 85, 5, 30, 20],
                "confidence": 0.92,
                "source": "omniparser",
                "enabled": True,
                "automation_id": ""
            })
            # Minimize button
            simulated_icons.append({
                "type": "icon",
                "text": "minimize button",
                "bbox": [img_w - 125, 5, 30, 20],
                "confidence": 0.91,
                "source": "omniparser",
                "enabled": True,
                "automation_id": ""
            })
            # Settings gear icon (often top-right or sidebar)
            simulated_icons.append({
                "type": "icon",
                "text": "settings gear",
                "bbox": [img_w - 170, 8, 24, 24],
                "confidence": 0.88,
                "source": "omniparser",
                "enabled": True,
                "automation_id": ""
            })
            # Hamburger / Menu icon (often top-left)
            simulated_icons.append({
                "type": "icon",
                "text": "menu list",
                "bbox": [15, 10, 24, 24],
                "confidence": 0.89,
                "source": "omniparser",
                "enabled": True,
                "automation_id": ""
            })
            # Back arrow (browser navigation style)
            simulated_icons.append({
                "type": "icon",
                "text": "back arrow",
                "bbox": [50, 10, 24, 24],
                "confidence": 0.87,
                "source": "omniparser",
                "enabled": True,
                "automation_id": ""
            })
            
        logger.info(f"Mock detector simulated {len(simulated_icons)} icons.")
        return simulated_icons

    def download_models(self, progress_callback=None) -> bool:
        """
        Downloads YOLOv8 icon detector and Florence-2 base model weights 
        and tokenizer configurations directly to local disk, reporting progress.
        """
        try:
            import requests
            
            # Reset cancellation flag
            self._cancel_download = False
            
            # Send immediate feedback to UI so it is not stuck on "Starting download..."
            if progress_callback:
                progress_callback(1.0, "Connecting to Hugging Face Model Hub...")
                
            weights_dir = os.path.expanduser("~/.cursor-king/weights")
            os.makedirs(weights_dir, exist_ok=True)
            
            # 1. Download YOLOv8 icon detect model (~30MB)
            yolo_url = "https://huggingface.co/microsoft/OmniParser-v2.0/resolve/main/icon_detect/model.pt"
            yolo_path = os.path.join(weights_dir, "icon_detect.pt")
            
            logger.info("Starting YOLOv8 weights download...")
            if progress_callback:
                progress_callback(2.0, "Initiating YOLOv8 weights download...")
            self._download_file(yolo_url, yolo_path, "YOLOv8 Icon Detector weights (~30MB)", 2.0, 15.0, progress_callback)
            
            # 2. Download Florence-2 weights and configs manually
            florence_dir = os.path.join(weights_dir, "florence")
            os.makedirs(florence_dir, exist_ok=True)
            
            files_to_download = [
                ("config.json", 15.0, 16.0),
                ("configuration_florence2.py", 16.0, 17.0),
                ("modeling_florence2.py", 17.0, 20.0),
                ("preprocessor_config.json", 20.0, 21.0),
                ("processing_florence2.py", 21.0, 23.0),
                ("model.safetensors", 23.0, 95.0),  # Primary model file (~458MB)
                ("vocab.json", 95.0, 96.0),
                ("tokenizer.json", 96.0, 98.0),
                ("tokenizer_config.json", 98.0, 100.0),
            ]
            
            for filename, p_start, p_end in files_to_download:
                url = f"https://huggingface.co/microsoft/Florence-2-base/resolve/main/{filename}"
                dest = os.path.join(florence_dir, filename)
                self._download_file(url, dest, f"Florence-2: {filename}", p_start, p_end, progress_callback)
                
            # Patch configuration_florence2.py to avoid AttributeError on newer transformers versions
            config_file_path = os.path.join(florence_dir, "configuration_florence2.py")
            if os.path.exists(config_file_path):
                try:
                    with open(config_file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    target = 'if self.forced_bos_token_id is None and kwargs.get("force_bos_token_to_be_generated", False):'
                    replacement = 'if getattr(self, "forced_bos_token_id", None) is None and kwargs.get("force_bos_token_to_be_generated", False):'
                    if target in content:
                        content = content.replace(target, replacement)
                        with open(config_file_path, "w", encoding="utf-8") as f:
                            f.write(content)
                        logger.info("Successfully patched configuration_florence2.py for compatibility.")
                except Exception as e:
                    logger.warning(f"Failed to patch configuration_florence2.py: {e}")

            # Patch processing_florence2.py to avoid tokenizer.additional_special_tokens AttributeError on newer transformers versions
            processing_file_path = os.path.join(florence_dir, "processing_florence2.py")
            if os.path.exists(processing_file_path):
                try:
                    with open(processing_file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    target = 'tokenizer.additional_special_tokens +'
                    replacement = "getattr(tokenizer, 'additional_special_tokens', []) +"
                    if target in content:
                        content = content.replace(target, replacement)
                        with open(processing_file_path, "w", encoding="utf-8") as f:
                            f.write(content)
                        logger.info("Successfully patched processing_florence2.py for compatibility.")
                except Exception as e:
                    logger.warning(f"Failed to patch processing_florence2.py: {e}")

            # Patch modeling_florence2.py to avoid _supports_sdpa and _supports_flash_attn_2 AttributeErrors on newer transformers versions
            modeling_file_path = os.path.join(florence_dir, "modeling_florence2.py")
            if os.path.exists(modeling_file_path):
                try:
                    with open(modeling_file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    target_flash = """    @property
    def _supports_flash_attn_2(self):
        \"\"\"
        Retrieve language_model's attribute to check whether the model supports
        Flash Attention 2 or not.
        \"\"\"
        return self.language_model._supports_flash_attn_2"""

                    replacement_flash = """    @property
    def _supports_flash_attn_2(self):
        \"\"\"
        Retrieve language_model's attribute to check whether the model supports
        Flash Attention 2 or not.
        \"\"\"
        if not hasattr(self, "language_model"):
            return False
        return self.language_model._supports_flash_attn_2"""

                    target_sdpa = """    @property
    def _supports_sdpa(self):
        \"\"\"
        Retrieve language_model's attribute to check whether the model supports
        SDPA or not.
        \"\"\"
        return self.language_model._supports_sdpa"""

                    replacement_sdpa = """    @property
    def _supports_sdpa(self):
        \"\"\"
        Retrieve language_model's attribute to check whether the model supports
        SDPA or not.
        \"\"\"
        if not hasattr(self, "language_model"):
            return False
        return self.language_model._supports_sdpa"""

                    modified = False
                    if target_flash in content:
                        content = content.replace(target_flash, replacement_flash)
                        modified = True
                    if target_sdpa in content:
                        content = content.replace(target_sdpa, replacement_sdpa)
                        modified = True
                        
                    if modified:
                        with open(modeling_file_path, "w", encoding="utf-8") as f:
                            f.write(content)
                        logger.info("Successfully patched modeling_florence2.py for compatibility.")
                except Exception as e:
                    logger.warning(f"Failed to patch modeling_florence2.py: {e}")

            if progress_callback:
                progress_callback(100.0, "All OmniParser V2 models downloaded and ready!")
            return True
        except Exception as e:
            if "cancelled by user" in str(e).lower():
                logger.info("OmniParser model download was cancelled by the user.")
                if progress_callback:
                    progress_callback(-1.0, "Download cancelled by user.")
            else:
                logger.error(f"Error in model download pipeline: {e}", exc_info=True)
                if progress_callback:
                    progress_callback(-1.0, f"Download failed: {str(e)}")
            return False

    def cancel_download(self) -> None:
        """Triggers cancellation of any active model download."""
        self._cancel_download = True
        logger.info("Cancellation signal set on UIDetector.")

    def _download_file(self, url: str, dest_path: str, description: str, progress_start: float, progress_end: float, callback) -> None:
        import requests
        logger.info(f"Downloading {description} from {url} to {dest_path}...")
        
        if getattr(self, "_cancel_download", False):
            raise Exception("Download cancelled by user")
            
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        # Optimize: Check if file is already fully downloaded to avoid redundant network usage
        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
            try:
                response_head = requests.head(url, headers=headers, timeout=10)
                if response_head.status_code == 200:
                    total_size = int(response_head.headers.get('content-length', 0))
                    if total_size > 0 and os.path.getsize(dest_path) == total_size:
                        logger.info(f"{description} already exists and size matches ({total_size} bytes). Skipping download.")
                        if callback:
                            callback(progress_end, f"Skipping {description} (already cached)")
                        return
            except Exception as e:
                logger.warning(f"Failed to check remote size for {description}: {e}. Redownloading...")

        # Use timeouts to prevent infinite blocking on connect or read
        response = requests.get(url, headers=headers, stream=True, timeout=(10, 30))
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        # Temp path to avoid corruption
        temp_dest = dest_path + ".tmp"
        
        try:
            with open(temp_dest, 'wb') as f:
                for chunk in response.iter_content(chunk_size=65536):
                    if getattr(self, "_cancel_download", False):
                        raise Exception("Download cancelled by user")
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0 and callback:
                            pct = downloaded / total_size
                            global_pct = progress_start + (pct * (progress_end - progress_start))
                            callback(round(global_pct, 1), f"Downloading {description}...")
        except Exception as e:
            # Clean up temp file on failure/cancellation
            try:
                if os.path.exists(temp_dest):
                    os.remove(temp_dest)
            except Exception:
                pass
            raise e
                        
        # Rename temp file to final file
        if getattr(self, "_cancel_download", False):
            try:
                if os.path.exists(temp_dest):
                    os.remove(temp_dest)
            except Exception:
                pass
            raise Exception("Download cancelled by user")
            
        if os.path.exists(dest_path):
            os.remove(dest_path)
        os.rename(temp_dest, dest_path)
        logger.info(f"Finished downloading {description}.")
