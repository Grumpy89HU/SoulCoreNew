"""
i18n fordító modul - Többnyelvű támogatás a SoulCore számára.
Minden felhasználónak megjelenő szöveg innen jön.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

class Translator:
    """
    Fordító osztály - kezeli a nyelvi fájlokat és a lokalizációt.
    
    Használat:
        t = Translator('hu')
        t.get('ui.welcome')  # "Üdvözöllek!"
    """
    
    # Támogatott nyelvek
    SUPPORTED_LANGUAGES = ['en', 'hu']
    DEFAULT_LANGUAGE = 'en'
    
    def __init__(self, language: str = None, locale_dir: str = None):
        """
        Inicializálás a kiválasztott nyelvvel.
        
        Args:
            language: Nyelvkód ('en', 'hu', stb.)
            locale_dir: A locale fájlok könyvtára (alapértelmezett: a fájl mellett lévő locales)
        """
        self.language = language or self.DEFAULT_LANGUAGE
        
        # Ha a kért nyelv nem támogatott, visszaállunk alapértelmezettre
        if self.language not in self.SUPPORTED_LANGUAGES:
            print(f"⚠️ Nyelv nem támogatott: {self.language}, visszaállás angolra")
            self.language = self.DEFAULT_LANGUAGE
        
        # Locale könyvtár beállítása
        if locale_dir is None:
            self.locale_dir = Path(__file__).parent / 'locales'
        else:
            self.locale_dir = Path(locale_dir)
        
        # Gyorsítótár a betöltött fordításokhoz
        self.cache: Dict[str, Dict[str, Any]] = {}
        
        # Betöltjük az összes fájlt az adott nyelvhez
        self._load_language(self.language)
        
        print(f"🌐 Fordító betöltve: {self.language}")
    
    def _load_language(self, language: str):
        """
        Betölti az adott nyelv összes JSON fájlját.
        """
        lang_dir = self.locale_dir / language
        
        if not lang_dir.exists():
            print(f"⚠️ Nyelvi könyvtár nem létezik: {lang_dir}")
            return
        
        # Az összes JSON fájl betöltése
        for json_file in lang_dir.glob('*.json'):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cache[json_file.stem] = data
                    print(f"   Betöltve: {json_file.name}")
            except Exception as e:
                print(f"⚠️ Hiba a nyelvi fájl betöltésekor {json_file}: {e}")
    
    def get(self, key: str, default: str = None, **kwargs) -> str:
        """
        Lekér egy fordítást a kulcs alapján.
        
        A kulcs lehet pontozott (pl. 'ui.welcome') vagy 'fájl.kulcs.alakulcs'.
        
        Args:
            key: A keresett kulcs (pl. 'ui.welcome' vagy 'errors.not_found')
            default: Alapértelmezett érték, ha nincs meg a kulcs
            **kwargs: Helyettesítendő paraméterek a szövegben (pl. name='Grumpy')
            
        Returns:
            A lefordított szöveg, vagy a kulcs ha nincs meg.
        """
        # Kulcs szétszedése: 'ui.welcome' -> ('ui', 'welcome')
        parts = key.split('.')
        
        if len(parts) < 2:
            # Nincs fájlnév a kulcsban, az összes fájlt átnézzük
            return self._search_in_all(key, default, **kwargs)
        
        file_name = parts[0]
        key_path = parts[1:]
        
        # Megkeressük a fájlt a cache-ben
        file_data = self.cache.get(file_name)
        if not file_data:
            return self._search_in_all(key, default, **kwargs)
        
        # Végigmegyünk a kulcs útvonalon
        current = file_data
        for k in key_path:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return self._search_in_all(key, default, **kwargs)
        
        # Ha string, akkor helyettesítjük a paraméterekkel
        if isinstance(current, str):
            return self._format(current, **kwargs)
        
        # Ha nem string, visszaadjuk a kulcsot vagy az alapértelmezettet
        return default or key
    
    def _search_in_all(self, key: str, default: str = None, **kwargs) -> str:
        """
        Átnézi az összes betöltött fájlt a kulcsra.
        """
        for file_data in self.cache.values():
            if isinstance(file_data, dict) and key in file_data:
                value = file_data[key]
                if isinstance(value, str):
                    return self._format(value, **kwargs)
                return str(value)
        
        return default or key
    
    def _format(self, text: str, **kwargs) -> str:
        """
        Helyettesíti a paramétereket a szövegben.
        
        Példa:
            text = "Hello {name}!"
            kwargs = {'name': 'Grumpy'}
            Eredmény: "Hello Grumpy!"
        """
        if not kwargs:
            return text
        
        try:
            return text.format(**kwargs)
        except KeyError as e:
            print(f"⚠️ Hiányzó paraméter a fordításban: {e}")
            return text
        except Exception as e:
            print(f"⚠️ Hiba a szöveg formázásakor: {e}")
            return text
    
    def set_language(self, language: str):
        """
        Átállítja a nyelvet.
        """
        if language == self.language:
            return
        
        if language in self.SUPPORTED_LANGUAGES:
            self.language = language
            self.cache.clear()
            self._load_language(language)
            print(f"🌐 Nyelv átállítva: {language}")
        else:
            print(f"⚠️ Nem támogatott nyelv: {language}")
    
    def get_supported_languages(self) -> list:
        """Visszaadja a támogatott nyelvek listáját."""
        return self.SUPPORTED_LANGUAGES

# Egyszerű használathoz globális példány (opcionális)
_default_translator = None

def get_translator(language: str = None) -> Translator:
    """
    Visszaad egy Translator példányt (singleton-szerű).
    """
    global _default_translator
    
    if language:
        if _default_translator is None:
            _default_translator = Translator(language)
        else:
            _default_translator.set_language(language)
    
    return _default_translator or Translator()