"""
Model Wrapper - Modell betöltés és inferencia.
Támogatja a llama.cpp GGUF fájlokat.
"""

import os
import time
import threading
from typing import Optional, Dict, Any, Generator

# Llama CPP import (ha nincs, fallback dummy)
try:
    from llama_cpp import Llama
    LLAMA_AVAILABLE = True
except ImportError:
    LLAMA_AVAILABLE = False
    print("⚠️ llama-cpp-python nem elérhető. Dummy módban futok.")

class ModelWrapper:
    """
    Modell betöltő és futtató.
    
    - GGUF fájl betöltése
    - Inferencia (szöveg generálás)
    - GPU használat (ha van)
    - Állapot figyelés (Jesternek)
    """
    
    def __init__(self, model_path: str, config: Dict = None):
        self.model_path = model_path
        self.config = config or {}
        self.model = None
        self.llama_available = LLAMA_AVAILABLE
        
        # Állapot
        self.state = {
            'loaded': False,
            'loading_time': None,
            'last_inference': None,
            'inference_count': 0,
            'total_tokens': 0,
            'average_speed': 0,  # token/sec
            'error': None
        }
        
        # Lock a thread safetyhez
        self.lock = threading.Lock()
        
        print(f"📦 ModelWrapper: {os.path.basename(model_path)}")
    
    def load(self) -> bool:
        if not self.llama_available:
            print("⚠️ Dummy mód: modell nem töltődik be")
            self.state['loaded'] = True  # Dummy módban sikeres
            return True
        
        try:
            start = time.time()
            print(f"⏳ Modell betöltés: {self.model_path}")
            
            # Debug: teljes konfig kiírása
            print(f"   Teljes konfig: {self.config}")
            
            # GPU rétegek száma (ha van CUDA)
            n_gpu_layers = self.config.get('n_gpu_layers', -1)  # -1 = minden GPU-ra
            print(f"   GPU rétegek értéke: {n_gpu_layers} (típus: {type(n_gpu_layers)})")
            
            if n_gpu_layers > 0:
                print(f"   GPU rétegek: {n_gpu_layers if n_gpu_layers > 0 else 'összes'}")
            
            # Kontextus méret
            n_ctx = self.config.get('n_ctx', 4096)
            print(f"   Kontextus: {n_ctx}")
            
            self.model = Llama(
                model_path=self.model_path,
                n_ctx=n_ctx,
                n_gpu_layers=n_gpu_layers,
                verbose=True  # <-- ÁLLÍTSD TRUE-RA
            )
            
            load_time = time.time() - start
            self.state['loaded'] = True
            self.state['loading_time'] = load_time
            self.state['n_ctx'] = n_ctx
            
            print(f"✅ Modell betöltve: {load_time:.1f} másodperc")
            print(f"   Kontextus: {n_ctx} token")
            return True
            
        except Exception as e:
            self.state['error'] = str(e)
            print(f"❌ Modell betöltési hiba: {e}")
            import traceback
            traceback.print_exc()  # <-- TELJES STACK TRACE
            return False
    
    def generate(self, 
                 prompt: str, 
                 max_tokens: int = 512,
                 temperature: float = 0.7,
                 top_p: float = 0.9,
                 stop: list = None) -> str:
        """
        Szöveg generálás a modellből.
        """
        with self.lock:
            if not self.state['loaded']:
                success = self.load()
                if not success:
                    return "[Modell nem elérhető]"
            
            start = time.time()
            start_tokens = self.state['total_tokens']
            
            try:
                if self.llama_available and self.model:
                    # Valós generálás
                    output = self.model(
                        prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        top_p=top_p,
                        stop=stop or [],
                        echo=False
                    )
                    text = output['choices'][0]['text']
                    tokens_used = output['usage']['completion_tokens']
                else:
                    # Dummy mód (teszteléshez)
                    time.sleep(0.5)  # Szimulált számolás
                    text = f"Ezt kaptam: {prompt[:50]}... (dummy válasz)"
                    tokens_used = len(text.split())
                
                # Statisztika frissítés
                inference_time = time.time() - start
                self.state['last_inference'] = time.time()
                self.state['inference_count'] += 1
                self.state['total_tokens'] += tokens_used
                
                # Mozgóátlag számítás
                speed = tokens_used / inference_time if inference_time > 0 else 0
                if self.state['average_speed'] == 0:
                    self.state['average_speed'] = speed
                else:
                    self.state['average_speed'] = self.state['average_speed'] * 0.9 + speed * 0.1
                
                return text
                
            except Exception as e:
                self.state['error'] = str(e)
                return f"[Hiba: {e}]"
    
    def generate_stream(self, 
                        prompt: str, 
                        max_tokens: int = 512,
                        temperature: float = 0.7) -> Generator[str, None, None]:
        """
        Streamezett generálás (tokenenként).
        """
        if not self.state['loaded']:
            success = self.load()
            if not success:
                yield "[Modell nem elérhető]"
                return
        
        try:
            if self.llama_available and self.model:
                # Streamezett generálás
                for chunk in self.model(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=True
                ):
                    token = chunk['choices'][0]['text']
                    if token:
                        yield token
            else:
                # Dummy stream
                words = prompt.split()
                for word in words[:10]:
                    time.sleep(0.1)
                    yield word + " "
                yield "(dummy stream vége)"
                
        except Exception as e:
            yield f"[Hiba: {e}]"
    
    def unload(self):
        """Modell kiürítése a memóriából"""
        with self.lock:
            if self.model:
                del self.model
                self.model = None
            self.state['loaded'] = False
            print("📦 Modell kiürítve")
    
    def get_state(self) -> Dict:
        """Állapot lekérése (Jesternek)"""
        return self.state

# Teszt
if __name__ == "__main__":
    # Dummy modell teszt
    mw = ModelWrapper("dummy_path.gguf")
    mw.load()
    
    response = mw.generate("Szia, hogy vagy?")
    print(f"Válasz: {response}")
    print(f"Állapot: {mw.get_state()}")
