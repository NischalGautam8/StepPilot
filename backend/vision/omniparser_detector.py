"""
OmniParser detector for icon and button detection using YOLOv8 and Florence-2.
Supports model downloading and lazy loading.
"""
import os
import logging
import numpy as np
from typing import List, Dict, Any, Optional
from pathlib import Path
import requests
from tqdm import tqdm

logger = logging.getLogger("cursor-king-backend.omniparser")

# Model URLs and paths
MODELS_DIR = Path.home() / ".cursor-king" / "models" / "omniparser"
YOLO_MODEL_URL = "https://huggingface.co/microsoft/OmniParser/resolve/main/icon_detect/best.pt"
FLORENCE_MODEL_URL = "https://huggingface.co/microsoft/OmniParser/resolve/main/icon_caption_florence"
YOLO_MODEL_PATH = MODELS_DIR / "icon_detect_best.pt"
FLORENCE_MODEL_PATH = MODELS_DIR / "icon_caption_florence"


class OmniParserDetector:
    """
    OmniParser detector for detecting icons and buttons in screenshots.
    Uses YOLOv8 for detection and Florence-2 for captioning.
    """
    
    def __init__(self, use_gpu: bool = False):
        self.use_gpu = use_gpu
        self.yolo_model = None
        self.florence_model = None
        self.florence_processor = None
        self._models_loaded = False
        
        # Ensure models directory exists
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        
    @staticmethod
    def are_models_downloaded() -> bool:
        """Check if OmniParser models are downloaded"""
        yolo_exists = YOLO_MODEL_PATH.exists()
        florence_exists = FLORENCE_MODEL_PATH.exists() and (FLORENCE_MODEL_PATH / "config.json").exists()
        return yolo_exists and florence_exists
        
    @staticmethod
    def download_models(progress_callback: Optional[callable] = None) -> bool:
        """
        Download OmniParser models from HuggingFace.
        
        Args:
            progress_callback: Optional callback function(current, total, status_message)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Starting OmniParser models download...")
            
            # Create models directory
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            
            # Download YOLO model
            if not YOLO_MODEL_PATH.exists():
                logger.info(f"Downloading YOLO model from {YOLO_MODEL_URL}...")
                if progress_callback:
                    progress_callback(0, 100, "Downloading YOLO icon detection model...")
                    
                response = requests.get(YOLO_MODEL_URL, stream=True)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(YOLO_MODEL_PATH, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback and total_size > 0:
                                progress = int((downloaded / total_size) * 50)  # 0-50%
                                progress_callback(progress, 100, f"Downloading YOLO model: {downloaded}/{total_size} bytes")
                                
                logger.info(f"YOLO model downloaded to {YOLO_MODEL_PATH}")
            else:
                logger.info("YOLO model already exists")
                if progress_callback:
                    progress_callback(50, 100, "YOLO model already downloaded")
            
            # Download Florence-2 model (using transformers library)
            if not FLORENCE_MODEL_PATH.exists() or not (FLORENCE_MODEL_PATH / "config.json").exists():
                logger.info("Downloading Florence-2 model...")
                if progress_callback:
                    progress_callback(50, 100, "Downloading Florence-2 caption model...")
                
                try:
                    from transformers import AutoProcessor, AutoModelForCausalLM
                    
                    # Download and save model
                    processor = AutoProcessor.from_pretrained(
                        "microsoft/Florence-2-base",
                        trust_remote_code=True
                    )
                    model = AutoModelForCausalLM.from_pretrained(
                        "microsoft/Florence-2-base",
                        trust_remote_code=True
                    )
                    
                    # Save to local directory
                    FLORENCE_MODEL_PATH.mkdir(parents=True, exist_ok=True)
                    processor.save_pretrained(FLORENCE_MODEL_PATH)
                    model.save_pretrained(FLORENCE_MODEL_PATH)
                    
                    logger.info(f"Florence-2 model downloaded to {FLORENCE_MODEL_PATH}")
                    if progress_callback:
                        progress_callback(100, 100, "All models downloaded successfully!")
                        
                except ImportError:
                    logger.error("transformers library not installed. Install with: pip install transformers")
                    return False
            else:
                logger.info("Florence-2 model already exists")
                if progress_callback:
                    progress_callback(100, 100, "All models already downloaded")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to download OmniParser models: {e}", exc_info=True)
            if progress_callback:
                progress_callback(0, 100, f"Download failed: {str(e)}")
            return False
    
    def load_models(self):
        """Load OmniParser models into memory (lazy loading)"""
        if self._models_loaded:
            return
            
        if not self.are_models_downloaded():
            raise RuntimeError(
                "OmniParser models not downloaded. "
                "Please download models first using download_models() or through settings."
            )
        
        try:
            logger.info("Loading OmniParser models...")
            
            # Load YOLO model
            try:
                from ultralytics import YOLO
                device = 'cuda' if self.use_gpu else 'cpu'
                self.yolo_model = YOLO(str(YOLO_MODEL_PATH))
                self.yolo_model.to(device)
                logger.info(f"YOLO model loaded on {device}")
            except ImportError:
                logger.error("ultralytics not installed. Install with: pip install ultralytics")
                raise
            
            # Load Florence-2 model
            try:
                from transformers import AutoProcessor, AutoModelForCausalLM
                import torch
                
                self.florence_processor = AutoProcessor.from_pretrained(
                    str(FLORENCE_MODEL_PATH),
                    trust_remote_code=True
                )
                self.florence_model = AutoModelForCausalLM.from_pretrained(
                    str(FLORENCE_MODEL_PATH),
                    trust_remote_code=True
                )
                
                if self.use_gpu and torch.cuda.is_available():
                    self.florence_model = self.florence_model.cuda()
                    logger.info("Florence-2 model loaded on GPU")
                else:
                    logger.info("Florence-2 model loaded on CPU")
                    
            except ImportError:
                logger.error("transformers not installed. Install with: pip install transformers torch")
                raise
            
            self._models_loaded = True
            logger.info("OmniParser models loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load OmniParser models: {e}", exc_info=True)
            raise
    
    async def detect(self, image_np: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect icons and buttons in an image.
        
        Args:
            image_np: Image as numpy array (BGR format from OpenCV)
            
        Returns:
            List of detected elements with format:
            [{
                "id": "omni_1",
                "type": "Icon" or "Button",
                "text": "caption from Florence-2",
                "bbox": [x, y, w, h],
                "confidence": 0.95,
                "source": "omniparser"
            }]
        """
        if not self._models_loaded:
            self.load_models()
        
        try:
            elements = []
            
            # Run YOLO detection
            results = self.yolo_model(image_np, verbose=False)
            
            # Process each detection
            for idx, result in enumerate(results[0].boxes):
                # Get bounding box
                x1, y1, x2, y2 = result.xyxy[0].cpu().numpy()
                x, y, w, h = int(x1), int(y1), int(x2 - x1), int(y2 - y1)
                confidence = float(result.conf[0])
                
                # Crop region for captioning
                crop = image_np[y:y+h, x:x+w]
                
                # Generate caption using Florence-2
                caption = await self._generate_caption(crop)
                
                # Determine type (Icon or Button based on size/aspect ratio)
                aspect_ratio = w / h if h > 0 else 1.0
                element_type = "Button" if aspect_ratio > 2.0 else "Icon"
                
                elements.append({
                    "id": f"omni_{idx + 1}",
                    "type": element_type,
                    "text": caption,
                    "bbox": [x, y, w, h],
                    "confidence": confidence,
                    "source": "omniparser",
                    "enabled": True,
                    "automation_id": None
                })
            
            logger.info(f"OmniParser detected {len(elements)} icons/buttons")
            return elements
            
        except Exception as e:
            logger.error(f"OmniParser detection failed: {e}", exc_info=True)
            return []
    
    async def _generate_caption(self, image_crop: np.ndarray) -> str:
        """Generate caption for an image crop using Florence-2"""
        try:
            from PIL import Image
            import torch
            
            # Convert BGR to RGB
            image_rgb = image_crop[:, :, ::-1]
            pil_image = Image.fromarray(image_rgb)
            
            # Prepare inputs
            prompt = "<CAPTION>"
            inputs = self.florence_processor(
                text=prompt,
                images=pil_image,
                return_tensors="pt"
            )
            
            if self.use_gpu and torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}
            
            # Generate caption
            with torch.no_grad():
                generated_ids = self.florence_model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=50,
                    num_beams=3
                )
            
            caption = self.florence_processor.batch_decode(
                generated_ids,
                skip_special_tokens=True
            )[0]
            
            return caption.strip()
            
        except Exception as e:
            logger.error(f"Caption generation failed: {e}")
            return "icon"


# Global instance (lazy loaded)
_omniparser_instance: Optional[OmniParserDetector] = None


def get_omniparser_detector(use_gpu: bool = False) -> OmniParserDetector:
    """Get or create OmniParser detector instance"""
    global _omniparser_instance
    if _omniparser_instance is None:
        _omniparser_instance = OmniParserDetector(use_gpu=use_gpu)
    return _omniparser_instance
