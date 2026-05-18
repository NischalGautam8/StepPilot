import logging

logger = logging.getLogger("cursor-king-backend.element-merger")

class ElementMerger:
    """
    ElementMerger dedupes and merges elements discovered via raw OCR
    and the native Windows Accessibility (UIA) tree.
    """
    def __init__(self, iou_threshold: float = 0.7):
        self.iou_threshold = iou_threshold

    @staticmethod
    def compute_iou(box1: list[int], box2: list[int]) -> float:
        """
        Computes Intersection over Union (IoU) of two bounding boxes in [x, y, w, h] format.
        """
        x1, y1, w1, h1 = box1
        x2, y2, w2, h2 = box2
        
        # Calculate coordinate boundaries
        x1_min, y1_min, x1_max, y1_max = x1, y1, x1 + w1, y1 + h1
        x2_min, y2_min, x2_max, y2_max = x2, y2, x2 + w2, y2 + h2
        
        # Find intersection overlap area
        inter_left = max(x1_min, x2_min)
        inter_top = max(y1_min, y2_min)
        inter_right = min(x1_max, x2_max)
        inter_bottom = min(y1_max, y2_max)
        
        inter_w = max(0, inter_right - inter_left)
        inter_h = max(0, inter_bottom - inter_top)
        inter_area = inter_w * inter_h
        
        if inter_area == 0:
            return 0.0
            
        # Areas of both boxes
        area1 = w1 * h1
        area2 = w2 * h2
        
        union_area = area1 + area2 - inter_area
        return inter_area / union_area if union_area > 0 else 0.0

    @staticmethod
    def compute_containment(inner_box: list[int], outer_box: list[int]) -> float:
        """
        Computes the ratio of inner_box that is contained inside outer_box.
        Useful when OCR text is wrapped inside a much larger UIA button.
        """
        x1, y1, w1, h1 = inner_box
        x2, y2, w2, h2 = outer_box
        
        x1_min, y1_min, x1_max, y1_max = x1, y1, x1 + w1, y1 + h1
        x2_min, y2_min, x2_max, y2_max = x2, y2, x2 + w2, y2 + h2
        
        inter_left = max(x1_min, x2_min)
        inter_top = max(y1_min, y2_min)
        inter_right = min(x1_max, x2_max)
        inter_bottom = min(y1_max, y2_max)
        
        inter_w = max(0, inter_right - inter_left)
        inter_h = max(0, inter_bottom - inter_top)
        inter_area = inter_w * inter_h
        
        inner_area = w1 * h1
        return inter_area / inner_area if inner_area > 0 else 0.0

    def merge(self, ocr_elements: list[dict], a11y_elements: list[dict]) -> list[dict]:
        """
        Combines OCR texts and Accessibility controls.
        
        Rules:
        - If an OCR text element overlaps (IoU > iou_threshold) or is highly contained (>80%) 
          inside an A11y control, they merge.
          - Prefer A11y control type, bounding box, enabled, automation_id
          - Prefer OCR text content (or fallback to A11y name)
          - Set source as "merged"
        - Unmerged A11y elements are kept with source "a11y"
        - Unmerged OCR elements are kept with type "Text" and source "ocr"
        - All final elements get a unique sequential string ID starting with "elem_"
        """
        merged_list = []
        used_ocr_indices = set()
        
        # Copy a11y elements as base
        temp_a11y = [dict(elem) for elem in a11y_elements]
        
        for a11y_idx, a11y in enumerate(temp_a11y):
            best_ocr_idx = -1
            best_metric = 0.0
            
            for ocr_idx, ocr in enumerate(ocr_elements):
                if ocr_idx in used_ocr_indices:
                    continue
                
                iou = self.compute_iou(ocr["bbox"], a11y["bbox"])
                containment = self.compute_containment(ocr["bbox"], a11y["bbox"])
                
                # We use IoU primary, fallback to containment if the OCR element is small and inside A11y
                metric = max(iou, containment * 0.85)
                
                if metric > self.iou_threshold or containment > 0.8:
                    if metric > best_metric:
                        best_metric = metric
                        best_ocr_idx = ocr_idx
            
            if best_ocr_idx != -1:
                # Merge OCR text content into A11y element
                ocr_elem = ocr_elements[best_ocr_idx]
                used_ocr_indices.add(best_ocr_idx)
                
                # Merge logic: prefer A11y's structural properties, OCR's visual text
                merged_elem = {
                    "type": a11y["type"],
                    "text": ocr_elem["text"] if ocr_elem["text"] else a11y["name"],
                    "bbox": a11y["bbox"],
                    "confidence": ocr_elem["confidence"],
                    "source": "merged",
                    "enabled": a11y["enabled"],
                    "automation_id": a11y["automation_id"]
                }
                merged_list.append(merged_elem)
            else:
                # Keep original A11y element
                merged_list.append({
                    "type": a11y["type"],
                    "text": a11y["name"],
                    "bbox": a11y["bbox"],
                    "confidence": 1.0,
                    "source": "a11y",
                    "enabled": a11y["enabled"],
                    "automation_id": a11y["automation_id"]
                }
            )
            
        # Add remaining OCR elements that didn't match any UIA control
        for ocr_idx, ocr in enumerate(ocr_elements):
            if ocr_idx not in used_ocr_indices:
                merged_list.append({
                    "type": "Text",
                    "text": ocr["text"],
                    "bbox": ocr["bbox"],
                    "confidence": ocr["confidence"],
                    "source": "ocr",
                    "enabled": True,
                    "automation_id": ""
                })
                
        # Assign unique element IDs
        final_elements = []
        for index, elem in enumerate(merged_list):
            elem["id"] = f"elem_{index + 1}"
            final_elements.append(elem)
            
        logger.info(f"ElementMerger outputted {len(final_elements)} unified UIElements.")
        return final_elements
