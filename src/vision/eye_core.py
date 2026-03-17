"""
Eye-Core - A Vár szeme.

Feladata:
1. Képek feldolgozása - amit a felhasználó mutat, azt a rendszer "látja"
2. OCR (Optical Character Recognition) - szöveg felismerés képeken
3. Objektum detekció - mi van a képen
4. Arc felismerés - ki van a képen
5. Vizuális kontextus - a King számára értelmezhető formában

Minden képfeldolgozás eredménye egy JSON struktúra, amit a King megkap.
"""

import time
import base64
import json
import threading
import os
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union

# Opcionális importok - ha nincsenek, dummy mód
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
    NP_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    NP_AVAILABLE = False
    print("⚠️ Eye-Core: OpenCV/numpy nem elérhető. Korlátozott módban futok.")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

# i18n import (opcionális)
try:
    from src.i18n.translator import get_translator
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False

class EyeCore:
    """
    A Vár szeme - vizuális feldolgozás.
    
    Képes:
    - Képek betöltése (fájlból, base64-ből, URL-ből)
    - OCR (szövegfelismerés)
    - Objektum detekció (ha van modell)
    - Arc felismerés (ha van)
    - Vizuális kontextus összeállítása
    """
    
    def __init__(self, scratchpad, config: Dict = None):
        self.scratchpad = scratchpad
        self.name = "eyecore"
        self.config = config or {}
        
        # Fordító (később állítjuk be)
        self.translator = None
        if I18N_AVAILABLE:
            self.translator = get_translator('en')
        
        # Alapértelmezett konfiguráció
        default_config = {
            'enabled': True,
            'enable_ocr': True,
            'enable_object_detection': False,  # Alapból kikapcs, mert modell kell
            'enable_face_detection': False,
            'max_image_size': 1920,              # Max képméret (pixel)
            'cache_results': True,                # Eredmények gyorsítótárazása
            'cache_ttl': 3600,                     # 1 óra
            'default_language': 'hun',             # OCR nyelve
            'save_uploaded': False,                 # Feltöltött képek mentése
            'upload_path': 'data/uploads',
            'enable_url_fetch': True,               # URL-ről kép letöltés
            'max_url_size': 10 * 1024 * 1024,       # Max 10 MB
            'timeout': 10                            # Időtúllépés másodpercben
        }
        
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value
        
        # Gyorsítótár
        self.cache = {}
        
        # Állapot
        self.state = {
            'status': 'idle',
            'images_processed': 0,
            'ocr_performed': 0,
            'objects_detected': 0,
            'faces_detected': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'errors': [],
            'last_cleanup': time.time()
        }
        
        # Objektum detekció modell (ha van)
        self.object_model = None
        if self.config['enable_object_detection']:
            self._init_object_detection()
        
        # Feltöltési mappa létrehozása
        if self.config['save_uploaded']:
            upload_path = Path(self.config['upload_path'])
            upload_path.mkdir(parents=True, exist_ok=True)
        
        print("👁️ Eye-Core: A Vár szeme kinyílt.")
        if not CV2_AVAILABLE:
            print("   ⚠️ OpenCV nélkül (korlátozott mód)")
    
    def set_language(self, language: str):
        """Nyelv beállítása (i18n)"""
        if self.translator and I18N_AVAILABLE:
            self.translator.set_language(language)
    
    def start(self):
        """Eye-Core indítása"""
        self.state['status'] = 'ready'
        self.scratchpad.set_state('eyecore_status', 'ready', self.name)
        print("👁️ Eye-Core: Figyelek.")
    
    def stop(self):
        """Eye-Core leállítása"""
        self.state['status'] = 'stopped'
        self.scratchpad.set_state('eyecore_status', 'stopped', self.name)
        print("👁️ Eye-Core: Becsukom a szemem.")
    
    def _init_object_detection(self):
        """Objektum detekciós modell inicializálása"""
        # Itt lehet majd YOLO vagy más modell
        print("👁️ Eye-Core: Objektum detekció inicializálása...")
        self.state['errors'].append("Object detection not implemented yet")
    
    # --- KÉP FELDOLGOZÁS ---
    
    def process_image(self, image_data: Any, source: str = "unknown") -> Dict:
        """
        Kép feldolgozása.
        
        Bemenet lehet:
        - Fájlnév (string)
        - Base64 kódolt kép (data:image/png;base64,...)
        - URL (http://...)
        - Numpy array (ha OpenCV van)
        - PIL Image
        
        Visszaad: {
            'success': bool,
            'description': str,  # Emberi olvasható leírás
            'ocr_text': str,      # Felismert szöveg
            'objects': list,       # Detektált objektumok
            'faces': list,         # Detektált arcok
            'dimensions': dict,    # Kép mérete
            'format': str,         # Kép formátum
            'error': str,          # Hibaüzenet (ha van)
            'processing_time': float
        }
        """
        start_time = time.time()
        self.state['status'] = 'processing'
        
        result = {
            'success': False,
            'description': '',
            'ocr_text': '',
            'objects': [],
            'faces': [],
            'dimensions': {},
            'format': '',
            'error': '',
            'processing_time': 0,
            'source': source,
            'timestamp': time.time()
        }
        
        try:
            # 1. Kép betöltése
            image, img_format, dimensions = self._load_image(image_data)
            if image is None:
                result['error'] = self._get_message('load_failed')
                return result
            
            result['dimensions'] = dimensions
            result['format'] = img_format
            
            # 2. Gyorsítótár ellenőrzés
            cache_key = self._get_cache_key(image)
            if self.config['cache_results'] and cache_key in self.cache:
                cached = self.cache[cache_key]
                if time.time() - cached['time'] < self.config['cache_ttl']:
                    result.update(cached['result'])
                    result['from_cache'] = True
                    self.state['cache_hits'] += 1
                    result['processing_time'] = time.time() - start_time
                    self.state['status'] = 'idle'
                    return result
            
            self.state['cache_misses'] += 1
            
            # 3. OCR (ha van)
            if self.config['enable_ocr'] and TESSERACT_AVAILABLE:
                ocr_text = self._perform_ocr(image)
                if ocr_text:
                    result['ocr_text'] = ocr_text
                    self.state['ocr_performed'] += 1
            
            # 4. Objektum detekció (ha van)
            if self.config['enable_object_detection'] and self.object_model:
                objects = self._detect_objects(image)
                if objects:
                    result['objects'] = objects
                    self.state['objects_detected'] += len(objects)
            
            # 5. Arc detekció (ha van)
            if self.config['enable_face_detection'] and CV2_AVAILABLE:
                faces = self._detect_faces(image)
                if faces:
                    result['faces'] = faces
                    self.state['faces_detected'] += len(faces)
            
            # 6. Leírás generálása
            result['description'] = self._generate_description(result)
            
            # 7. Kép mentése (ha kell)
            if self.config['save_uploaded']:
                self._save_image(image, source)
            
            result['success'] = True
            
            # Gyorsítótárazás
            if self.config['cache_results']:
                self.cache[cache_key] = {
                    'result': result,
                    'time': time.time()
                }
            
        except Exception as e:
            result['error'] = str(e)
            self.state['errors'].append(str(e))
            print(f"👁️ Eye-Core hiba: {e}")
        
        finally:
            self.state['images_processed'] += 1
            self.state['status'] = 'idle'
            result['processing_time'] = time.time() - start_time
        
        return result
    
    def _load_image(self, image_data: Any) -> Tuple[Any, str, Dict]:
        """
        Kép betöltése különböző formátumokból.
        Visszaad: (image, format, dimensions)
        """
        if not CV2_AVAILABLE or not NP_AVAILABLE:
            return None, '', {}
        
        # 1. Ha már numpy array (OpenCV kép)
        if NP_AVAILABLE and isinstance(image_data, np.ndarray):
            h, w = image_data.shape[:2]
            channels = image_data.shape[2] if len(image_data.shape) > 2 else 1
            return image_data, 'array', {'width': w, 'height': h, 'channels': channels}
        
        # 2. Ha fájlnév
        if isinstance(image_data, str) and os.path.exists(image_data):
            img = cv2.imread(image_data)
            if img is not None:
                h, w = img.shape[:2]
                channels = img.shape[2] if len(img.shape) > 2 else 1
                return img, 'file', {'width': w, 'height': h, 'channels': channels}
        
        # 3. Ha URL
        if isinstance(image_data, str) and image_data.startswith(('http://', 'https://')):
            if self.config['enable_url_fetch']:
                return self._load_from_url(image_data)
        
        # 4. Ha base64
        if isinstance(image_data, str) and image_data.startswith('data:image'):
            try:
                # data:image/png;base64,...
                header, encoded = image_data.split(',', 1)
                img_data = base64.b64decode(encoded)
                nparr = np.frombuffer(img_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is not None:
                    h, w = img.shape[:2]
                    channels = img.shape[2] if len(img.shape) > 2 else 1
                    return img, 'base64', {'width': w, 'height': h, 'channels': channels}
            except Exception as e:
                print(f"👁️ Base64 betöltési hiba: {e}")
        
        # 5. Ha PIL Image
        if PIL_AVAILABLE and isinstance(image_data, Image.Image):
            img = cv2.cvtColor(np.array(image_data), cv2.COLOR_RGB2BGR)
            h, w = img.shape[:2]
            channels = img.shape[2] if len(img.shape) > 2 else 1
            return img, 'pil', {'width': w, 'height': h, 'channels': channels}
        
        return None, '', {}
    
    def _load_from_url(self, url: str) -> Tuple[Any, str, Dict]:
        """
        Kép betöltése URL-ről.
        """
        try:
            import requests
            from io import BytesIO
            
            response = requests.get(url, timeout=self.config['timeout'], stream=True)
            response.raise_for_status()
            
            # Méret ellenőrzés
            content_length = int(response.headers.get('content-length', 0))
            if content_length > self.config['max_url_size']:
                return None, '', {}
            
            img_data = response.content
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is not None:
                h, w = img.shape[:2]
                channels = img.shape[2] if len(img.shape) > 2 else 1
                return img, 'url', {'width': w, 'height': h, 'channels': channels}
            
        except Exception as e:
            print(f"👁️ URL betöltési hiba: {e}")
        
        return None, '', {}
    
    def _get_cache_key(self, image) -> str:  # Típusannotáció nélkül
        """Gyorsítótár kulcs generálása kép hash alapján"""
        if image is None or not NP_AVAILABLE:
            return ''
        
        try:
            # Kis méretű thumbnail a gyorsítótárhoz
            small = cv2.resize(image, (32, 32))
            hash_str = hashlib.md5(small.tobytes()).hexdigest()
            return hash_str
        except Exception as e:
            print(f"👁️ Cache key hiba: {e}")
            return ''
    
    def _perform_ocr(self, image) -> str:  # Típusannotáció nélkül
        """
        OCR (Optical Character Recognition) - szövegfelismerés.
        """
        if not TESSERACT_AVAILABLE or not CV2_AVAILABLE:
            return ""
        
        try:
            # Előfeldolgozás
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Szöveg felismerés
            text = pytesseract.image_to_string(
                gray, 
                lang=self.config['default_language'],
                config='--psm 3'
            )
            
            return text.strip()
        except Exception as e:
            print(f"👁️ OCR hiba: {e}")
            return ""
    
    def _detect_objects(self, image) -> List[Dict]:  # Típusannotáció nélkül
        """
        Objektum detekció.
        """
        # Itt majd YOLO vagy más modell
        return []
    
    def _detect_faces(self, image) -> List[Dict]:  # Típusannotáció nélkül
        """
        Arc detekció (ha van).
        """
        if not CV2_AVAILABLE:
            return []
        
        try:
            # Haar Cascade használata
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)
            
            result = []
            for (x, y, w, h) in faces:
                result.append({
                    'x': int(x),
                    'y': int(y),
                    'width': int(w),
                    'height': int(h),
                    'confidence': 0.9
                })
            
            return result
        except Exception as e:
            print(f"👁️ Arc detekció hiba: {e}")
            return []
    
    def _generate_description(self, result: Dict) -> str:
        """
        Emberi olvasható leírás generálása a feldolgozás eredményéből.
        Ezt kapja majd a King.
        """
        parts = []
        
        # Dimenziók
        dims = result.get('dimensions', {})
        if dims:
            parts.append(self._get_message('dimensions', 
                width=dims.get('width', '?'), 
                height=dims.get('height', '?')))
        
        # OCR szöveg
        ocr = result.get('ocr_text', '').strip()
        if ocr:
            if len(ocr) > 200:
                parts.append(self._get_message('ocr_text_long', text=ocr[:200]))
            else:
                parts.append(self._get_message('ocr_text', text=ocr))
        
        # Objektumok
        objects = result.get('objects', [])
        if objects:
            obj_names = [obj.get('name', 'unknown') for obj in objects[:5]]
            parts.append(self._get_message('objects_detected', 
                count=len(objects), 
                names=', '.join(obj_names)))
        
        # Arcok
        faces = result.get('faces', [])
        if faces:
            if len(faces) == 1:
                parts.append(self._get_message('one_face'))
            else:
                parts.append(self._get_message('multiple_faces', count=len(faces)))
        
        if not parts:
            return self._get_message('nothing_detected')
        
        return " ".join(parts)
    
    def _save_image(self, image, source: str):  # Típusannotáció nélkül
        """Kép mentése (debug célra)"""
        if not CV2_AVAILABLE:
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"eye_{timestamp}_{source}.jpg"
            filepath = Path(self.config['upload_path']) / filename
            cv2.imwrite(str(filepath), image)
        except Exception as e:
            print(f"👁️ Képmentési hiba: {e}")
    
    def _get_message(self, msg_type: str, **kwargs) -> str:
        """
        Üzenet lekérése i18n-ből vagy alapértelmezett angol.
        """
        if self.translator and I18N_AVAILABLE:
            return self.translator.get(f'vision.{msg_type}', **kwargs)
        
        # Alapértelmezett angol üzenetek
        fallbacks = {
            'dimensions': f"Image is {kwargs.get('width', '?')}x{kwargs.get('height', '?')} pixels.",
            'ocr_text': f"Text in image: {kwargs.get('text', '')}",
            'ocr_text_long': f"Text in image: {kwargs.get('text', '')}...",
            'objects_detected': f"Detected {kwargs.get('count', 0)} objects: {kwargs.get('names', '')}.",
            'one_face': "One face detected in the image.",
            'multiple_faces': f"{kwargs.get('count', 0)} faces detected in the image.",
            'nothing_detected': "Could not recognize anything in the image.",
            'load_failed': "Failed to load image."
        }
        
        return fallbacks.get(msg_type, str(kwargs))
    
    # --- KING INTEGRÁCIÓ ---
    
    def get_vision_context(self, image_data: Any) -> str:
        """
        Vizuális kontextus összeállítása a King számára.
        Ezt kapja majd a King a promptban.
        """
        result = self.process_image(image_data)
        
        if not result['success']:
            return f"[Vision error: {result['error']}]"
        
        # Összeállítás a Kingnek
        context_parts = ["[Vision information]"]
        context_parts.append(result['description'])
        
        if result['ocr_text']:
            if len(result['ocr_text']) > 500:
                context_parts.append(f"Recognized text: {result['ocr_text'][:500]}...")
            else:
                context_parts.append(f"Recognized text: {result['ocr_text']}")
        
        context_parts.append("[/Vision information]")
        
        return "\n".join(context_parts)
    
    # --- KARBANTARTÁS ---
    
    def cleanup_cache(self):
        """Régi cache bejegyzések törlése"""
        now = time.time()
        to_delete = []
        
        for key, entry in self.cache.items():
            if now - entry['time'] > self.config['cache_ttl']:
                to_delete.append(key)
        
        for key in to_delete:
            del self.cache[key]
        
        self.state['last_cleanup'] = now
        
        if to_delete:
            print(f"👁️ Eye-Core: {len(to_delete)} cache bejegyzés törölve")
    
    # --- ÁLLAPOT ---
    
    def get_state(self) -> Dict:
        """Állapot lekérése"""
        return {
            'status': self.state['status'],
            'images_processed': self.state['images_processed'],
            'ocr_performed': self.state['ocr_performed'],
            'objects_detected': self.state['objects_detected'],
            'faces_detected': self.state['faces_detected'],
            'errors': len(self.state['errors']),
            'cache': {
                'size': len(self.cache),
                'hits': self.state['cache_hits'],
                'misses': self.state['cache_misses']
            },
            'config': {
                'enable_ocr': self.config['enable_ocr'],
                'enable_object_detection': self.config['enable_object_detection'],
                'enable_face_detection': self.config['enable_face_detection']
            }
        }

# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    
    s = Scratchpad()
    eye = EyeCore(s)
    
    # Teszt (ha van kép)
    test_image = "test.jpg"
    if os.path.exists(test_image):
        result = eye.process_image(test_image)
        print(json.dumps(result, indent=2, default=str))
        print("\nKing context:")
        print(eye.get_vision_context(test_image))
    else:
        print("No test image found.")