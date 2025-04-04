from transformers import pipeline
from PIL import Image
import numpy as np
import cv2
import os
import torch
from tqdm import tqdm

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("⚠ Warning: YOLO not available, using basic detection only")

class EnhancedContentDetector:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        try:
            self.nsfw_model = pipeline(
                "image-classification",
                model="Falconsai/nsfw_image_detection",
                device=self.device
            )
        except Exception as e:
            print(f"⚠ Failed to load NSFW model: {str(e)}")
            self.nsfw_model = None

        self.object_model = None
        if YOLO_AVAILABLE:
            try:
                self.object_model = YOLO("yolov8n.pt")
                print("✅ YOLO model loaded successfully")
            except Exception as e:
                print(f"⚠ Failed to load YOLO model: {str(e)}")

        self.danger_categories = {
            "drugs": ["syringe", "pill", "joint", "pipe", "drug"],
            "weapons": ["gun", "knife", "rifle", "pistol", "weapon"],
            "violence": ["blood", "corpse", "handcuffs", "fight"]
        }

        self.nsfw_threshold = 0.7
        self.object_confidence = 0.6

    def detect_objects(self, image):
        if not self.object_model:
            return []

        try:
            results = self.object_model(image)
            detected = []

            for result in results:
                for box in result.boxes:
                    obj_class = self.object_model.names[int(box.cls)]
                    conf = float(box.conf)
                    if conf > self.object_confidence:
                        detected.append((obj_class.lower(), conf))
            return detected
        except Exception as e:
            print(f"⚠ Object detection error: {str(e)}")
            return []

    def analyze_content(self, detected_objects):
        violations = {category: False for category in self.danger_categories}
        dangerous_items = []

        for obj, conf in detected_objects:
            for category, keywords in self.danger_categories.items():
                if any(keyword in obj for keyword in keywords):
                    violations[category] = True
                    dangerous_items.append(f"{obj} ({conf:.2f})")
                    break

        return violations, dangerous_items

    def analyze_image(self, image_path):
        try:
            if not os.path.exists(image_path):
                return {"error": "File not found"}

            img = Image.open(image_path)
            img_cv = cv2.imread(image_path)

            result = {
                "file": os.path.basename(image_path),
                "verdict": "🟢 CLEAN",
                "violations": {},
                "details": {}
            }

            if self.nsfw_model:
                try:
                    nsfw_results = self.nsfw_model(img)
                    nsfw_score = next((r['score'] for r in nsfw_results if r['label'] == 'nsfw'), 0.0)
                    result['details']['nsfw_score'] = f"{nsfw_score * 100:.1f}%"
                    if nsfw_score > self.nsfw_threshold:
                        result['violations']['nudity'] = True
                except Exception as e:
                    print(f"⚠ NSFW analysis error: {str(e)}")

            if self.object_model:
                try:
                    detected_objects = self.detect_objects(img_cv)
                    object_violations, dangerous_items = self.analyze_content(detected_objects)
                    result['details']['detected_objects'] = detected_objects

                    for cat, detected in object_violations.items():
                        if detected:
                            result['violations'][cat] = True

                    if dangerous_items:
                        result['details']['dangerous_items'] = dangerous_items
                except Exception as e:
                    print(f"⚠ Object detection error: {str(e)}")

            if any(result['violations'].values()):
                result['verdict'] = "🔴 BANNED"

            return result

        except Exception as e:
            return {
                "file": os.path.basename(image_path),
                "error": str(e)
            }