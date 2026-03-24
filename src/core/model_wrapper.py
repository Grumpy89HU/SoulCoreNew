"""
Model Wrapper - Modell betöltés és inferencia.
Támogatja a llama.cpp GGUF fájlokat és split modelleket.
"""

import os
import time
import threading
from typing import Optional, Dict, Any, Generator, List, Union

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
    
    - GGUF fájl betöltése (egyedi vagy split)
    - Inferencia (szöveg generálás)
    - GPU használat (több GPU támogatás)
    - Állapot figyelés (Jesternek)
    - Split modellek támogatása (pl. 00001-of-00002)
    - Embedding támogatás (ha a modell embedding=True-val lett betöltve)
    """
    
    def __init__(self, model_path: str, config: Dict = None):
        self.model_path = model_path
        self.config = config or {}
        self.model = None
        self.llama_available = LLAMA_AVAILABLE
        self.is_split = False
        self.split_parts = []
        
        # Embedding támogatás jelző
        self.embedding_enabled = self.config.get('embedding', False)
        
        # Állapot
        self.state = {
            'loaded': False,
            'loading_time': None,
            'last_inference': None,
            'inference_count': 0,
            'total_tokens': 0,
            'average_speed': 0,  # token/sec
            'error': None,
            'gpu_layers': 0,
            'gpu_devices': [],
            'n_ctx': 0,
            'embedding_available': False
        }
        
        # Lock a thread safetyhez
        self.lock = threading.RLock()
        
        # Ellenőrizzük, hogy split modell-e
        self._check_split_model()
        
        print(f"📦 ModelWrapper: {os.path.basename(model_path)}")
        if self.is_split:
            print(f"   Split modell: {len(self.split_parts)} rész")
        if self.embedding_enabled:
            print(f"   Embedding támogatás: bekapcsolva")
    
    def _check_split_model(self):
        """
        Ellenőrzi, hogy a modell split-e (több fájlból áll).
        Pl.: valami-00001-of-00002.gguf
        """
        if not os.path.exists(self.model_path):
            # Lehet, hogy split modell része
            import glob
            pattern = self.model_path.replace('00001-of', '*')
            matching_files = glob.glob(pattern)
            
            if len(matching_files) > 1:
                self.is_split = True
                self.split_parts = sorted(matching_files)
                print(f"   Split modell részek: {self.split_parts}")
    
    def load(self) -> bool:
        """Modell betöltése a memóriába"""
        if not self.llama_available:
            print("⚠️ Dummy mód: modell nem töltődik be")
            self.state['loaded'] = True  # Dummy módban sikeres
            return True
        
        try:
            start = time.time()
            print(f"⏳ Modell betöltés: {self.model_path}")
            
            # GPU rétegek száma (ha van CUDA)
            n_gpu_layers = self.config.get('n_gpu_layers', -1)
            print(f"   GPU rétegek: {n_gpu_layers}")
            self.state['gpu_layers'] = n_gpu_layers
            
            # GPU eszközök megadása (ha több GPU van)
            main_gpu = self.config.get('main_gpu', 0)
            tensor_split = self.config.get('tensor_split', None)
            
            if tensor_split:
                print(f"   Tensor split: {tensor_split}")
                self.state['gpu_devices'] = tensor_split
            
            # Kontextus méret
            n_ctx = self.config.get('n_ctx', 4096)
            print(f"   Kontextus: {n_ctx}")
            
            # Embedding támogatás
            embedding = self.config.get('embedding', False)
            print(f"   Embedding: {embedding}")
            self.embedding_enabled = embedding
            
            # Split modell kezelés
            if self.is_split:
                model_path = self.split_parts[0]  # Az első rész
                print(f"   Split modell első része: {model_path}")
            else:
                model_path = self.model_path
            
            # Csak azokat a paramétereket adjuk át, amelyek nem None-ok
            params = {
                'model_path': model_path,
                'n_ctx': n_ctx,
                'n_gpu_layers': n_gpu_layers,
                'main_gpu': main_gpu,
                'verbose': self.config.get('verbose', False),
                'n_batch': self.config.get('n_batch', 512),
                'mul_mat_q': self.config.get('mul_mat_q', True),
                'logits_all': self.config.get('logits_all', False),
                'embedding': embedding,
                'offload_kqv': self.config.get('offload_kqv', True)
            }
            
            # Opcionális paraméterek - csak ha nem None
            if tensor_split is not None:
                params['tensor_split'] = tensor_split
            
            if self.config.get('n_threads') is not None:
                params['n_threads'] = self.config['n_threads']
            
            if self.config.get('n_threads_batch') is not None:
                params['n_threads_batch'] = self.config['n_threads_batch']
            
            # Rope paraméterek - csak ha nem None
            if self.config.get('rope_scaling_type') is not None:
                params['rope_scaling_type'] = self.config['rope_scaling_type']
            
            if self.config.get('rope_freq_base') is not None:
                params['rope_freq_base'] = self.config['rope_freq_base']
            
            if self.config.get('rope_freq_scale') is not None:
                params['rope_freq_scale'] = self.config['rope_freq_scale']
            
            if self.config.get('yarn_ext_factor') is not None:
                params['yarn_ext_factor'] = self.config['yarn_ext_factor']
            
            if self.config.get('yarn_attn_factor') is not None:
                params['yarn_attn_factor'] = self.config['yarn_attn_factor']
            
            if self.config.get('yarn_beta_fast') is not None:
                params['yarn_beta_fast'] = self.config['yarn_beta_fast']
            
            if self.config.get('yarn_beta_slow') is not None:
                params['yarn_beta_slow'] = self.config['yarn_beta_slow']
            
            if self.config.get('yarn_orig_ctx') is not None:
                params['yarn_orig_ctx'] = self.config['yarn_orig_ctx']
            
            # Modell betöltés
            self.model = Llama(**params)
            
            load_time = time.time() - start
            self.state['loaded'] = True
            self.state['loading_time'] = load_time
            self.state['n_ctx'] = n_ctx
            self.state['embedding_available'] = embedding
            
            print(f"✅ Modell betöltve: {load_time:.1f} másodperc")
            print(f"   Kontextus: {n_ctx} token")
            if embedding:
                print(f"   Embedding: elérhető")
            return True
            
        except Exception as e:
            self.state['error'] = str(e)
            print(f"❌ Modell betöltési hiba: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def generate(self, 
                 prompt: str, 
                 max_tokens: int = 512,
                 temperature: float = 0.7,
                 top_p: float = 0.9,
                 top_k: int = 40,
                 repeat_penalty: float = 1.1,
                 stop: list = None,
                 stream: bool = False) -> Union[str, Generator[str, None, None]]:
        """
        Szöveg generálás a modellből.
        
        Args:
            prompt: Bemeneti szöveg
            max_tokens: Maximum generálandó tokenek száma
            temperature: Hőmérséklet (0.1 - 2.0)
            top_p: Top-p sampling
            top_k: Top-k sampling
            repeat_penalty: Ismétlődés büntetés
            stop: Leállító tokenek listája
            stream: Streamezett generálás
        
        Returns:
            Generált szöveg vagy generator
        """
        with self.lock:
            if not self.state['loaded']:
                success = self.load()
                if not success:
                    return "[Modell nem elérhető]"
            
            start = time.time()
            
            try:
                if self.llama_available and self.model:
                    if stream:
                        return self._generate_stream(
                            prompt, max_tokens, temperature, 
                            top_p, top_k, repeat_penalty, stop
                        )
                    
                    # Valós generálás
                    output = self.model(
                        prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        top_p=top_p,
                        top_k=top_k,
                        repeat_penalty=repeat_penalty,
                        stop=stop or [],
                        echo=False
                    )
                    
                    if 'choices' in output and len(output['choices']) > 0:
                        text = output['choices'][0]['text']
                        tokens_used = output['usage']['completion_tokens']
                    else:
                        text = ""
                        tokens_used = 0
                else:
                    # Dummy mód (teszteléshez)
                    time.sleep(0.1 * (max_tokens / 100))
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
                error_msg = f"[Hiba: {e}]"
                return error_msg
    
    def _generate_stream(self, 
                         prompt: str, 
                         max_tokens: int = 512,
                         temperature: float = 0.7,
                         top_p: float = 0.9,
                         top_k: int = 40,
                         repeat_penalty: float = 1.1,
                         stop: list = None) -> Generator[str, None, None]:
        """
        Streamezett generálás (tokenenként).
        """
        try:
            if self.llama_available and self.model:
                for chunk in self.model(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    repeat_penalty=repeat_penalty,
                    stop=stop or [],
                    stream=True
                ):
                    if 'choices' in chunk and len(chunk['choices']) > 0:
                        token = chunk['choices'][0]['text']
                        if token:
                            yield token
            else:
                words = prompt.split()
                for word in words[:10]:
                    time.sleep(0.05)
                    yield word + " "
                yield "(dummy stream vége)"
                
        except Exception as e:
            yield f"[Hiba: {e}]"
    
    def create_completion(self, 
                         messages: List[Dict[str, str]],
                         max_tokens: int = 512,
                         temperature: float = 0.7) -> str:
        """
        Chat completion formátumú generálás.
        OpenAI-kompatibilis API.
        
        Args:
            messages: [{"role": "user", "content": "Hello"}, ...]
            max_tokens: Max token
            temperature: Hőmérséklet
        
        Returns:
            Generált válasz
        """
        if not self.model:
            return "[Modell nem elérhető]"
        
        try:
            output = self.model.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            if 'choices' in output and len(output['choices']) > 0:
                return output['choices'][0]['message']['content']
            return ""
            
        except Exception as e:
            return f"[Hiba: {e}]"
    
    def embed(self, text: str) -> List[float]:
        """
        Szöveg embedding vektorának lekérése.
        
        Fontos: A modellt embedding=True paraméterrel kell betölteni!
        """
        # Ellenőrizzük, hogy a modell támogatja-e az embeddinget
        if not self.model:
            print("📦 Embedding: modell nincs betöltve")
            return []
        
        if not self.embedding_enabled:
            print("📦 Embedding: a modell embedding támogatás nélkül lett betöltve")
            return []
        
        if not hasattr(self.model, 'embed'):
            print("📦 Embedding: a modell nem támogatja az embed metódust")
            return []
        
        try:
            return self.model.embed(text)
        except Exception as e:
            print(f"📦 Embedding hiba: {e}")
            return []
    
    def tokenize(self, text: str) -> List[int]:
        """
        Szöveg tokenizálása.
        """
        if not self.model:
            return []
        
        try:
            return self.model.tokenize(text.encode('utf-8'))
        except Exception as e:
            print(f"📦 Tokenizálási hiba: {e}")
            return []
    
    def detokenize(self, tokens: List[int]) -> str:
        """
        Tokenek visszaalakítása szöveggé.
        """
        if not self.model:
            return ""
        
        try:
            return self.model.detokenize(tokens)
        except Exception as e:
            print(f"📦 Detokenizálási hiba: {e}")
            return ""
    
    def unload(self):
        """Modell kiürítése a memóriából"""
        with self.lock:
            if self.model:
                del self.model
                self.model = None
            self.state['loaded'] = False
            self.state['embedding_available'] = False
            print("📦 Modell kiürítve")
    
    def get_state(self) -> Dict:
        """Állapot lekérése (Jesternek)"""
        return {
            'loaded': self.state['loaded'],
            'loading_time': self.state['loading_time'],
            'last_inference': self.state['last_inference'],
            'inference_count': self.state['inference_count'],
            'total_tokens': self.state['total_tokens'],
            'average_speed': round(self.state['average_speed'], 2),
            'gpu_layers': self.state['gpu_layers'],
            'gpu_devices': self.state['gpu_devices'],
            'n_ctx': self.state.get('n_ctx', 0),
            'embedding_available': self.state.get('embedding_available', False),
            'error': self.state['error'],
            'is_split': self.is_split,
            'split_parts': len(self.split_parts) if self.is_split else 0
        }
    
    def get_metrics(self) -> Dict:
        """Részletes metrikák lekérése (UI-nak)"""
        last_inference_ago = None
        if self.state['last_inference']:
            last_inference_ago = time.time() - self.state['last_inference']
        
        return {
            'inference_count': self.state['inference_count'],
            'total_tokens': self.state['total_tokens'],
            'average_speed': round(self.state['average_speed'], 2),
            'last_inference_ago': last_inference_ago,
            'gpu_usage': self.state.get('gpu_usage', {}),
            'vram_usage': self.state.get('vram_usage', 0),
            'embedding_available': self.state.get('embedding_available', False)
        }
    
    def set_embedding(self, enabled: bool):
        """
        Embedding támogatás beállítása (modell újratöltés szükséges).
        """
        self.embedding_enabled = enabled
        if enabled:
            self.config['embedding'] = True
        else:
            self.config['embedding'] = False
        
        # Ha a modell be van töltve, jelezzük, hogy újratöltés kell
        if self.state['loaded']:
            print("📦 Figyelem: embedding beállítás megváltozott, modell újratöltése szükséges!")
    
    def is_embedding_available(self) -> bool:
        """Embedding elérhetőségének lekérése"""
        return self.state.get('embedding_available', False)


# Teszt
if __name__ == "__main__":
    # Dummy modell teszt
    mw = ModelWrapper("dummy_path.gguf")
    mw.load()
    
    response = mw.generate("Szia, hogy vagy?")
    print(f"Válasz: {response}")
    print(f"Állapot: {mw.get_state()}")
    
    # Embedding teszt
    embedding = mw.embed("Teszt szöveg")
    print(f"Embedding: {embedding[:5] if embedding else 'üres'}")
    
    # Teszt split modellel
    mw2 = ModelWrapper("model-00001-of-00002.gguf")
    print(f"Split modell: {mw2.is_split}")