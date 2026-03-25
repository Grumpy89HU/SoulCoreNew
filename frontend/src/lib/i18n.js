import { writable, derived } from 'svelte/store';

const translations = {
  en: {
    'nav.chat': 'Chat',
    'nav.admin': 'Admin',
    'chat.placeholder': 'Type your message...',
    'chat.send': 'Send',
    'chat.typing': 'Typing...',
    'chat.new_conversation': 'New conversation',
    'chat.conversations': 'Conversations',
    'admin.dashboard': 'Dashboard',
    'admin.modules': 'Modules',
    'admin.models': 'Models',
    'admin.personalities': 'Personalities',
    'admin.prompts': 'Prompts',
    'admin.logs': 'Logs',
    'admin.metrics': 'Metrics',
    'admin.settings': 'Settings',
    'general.loading': 'Loading...',
    'general.error': 'Error',
    'general.success': 'Success',
    'general.save': 'Save',
    'general.cancel': 'Cancel',
    'general.delete': 'Delete'
  },
  hu: {
    'nav.chat': 'Beszélgetés',
    'nav.admin': 'Admin',
    'chat.placeholder': 'Írd ide az üzeneted...',
    'chat.send': 'Küldés',
    'chat.typing': 'Gépelés...',
    'chat.new_conversation': 'Új beszélgetés',
    'chat.conversations': 'Beszélgetések',
    'admin.dashboard': 'Vezérlőpult',
    'admin.modules': 'Modulok',
    'admin.models': 'Modellek',
    'admin.personalities': 'Személyiségek',
    'admin.prompts': 'Promptok',
    'admin.logs': 'Naplók',
    'admin.metrics': 'Metrikák',
    'admin.settings': 'Beállítások',
    'general.loading': 'Betöltés...',
    'general.error': 'Hiba',
    'general.success': 'Siker',
    'general.save': 'Mentés',
    'general.cancel': 'Mégse',
    'general.delete': 'Törlés'
  }
};

export const currentLanguage = writable('hu');

export const t = derived(currentLanguage, $lang => {
  const dict = translations[$lang] || translations.en;
  return (key, params = {}) => {
    let text = dict[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(`{${k}}`, v);
    });
    return text;
  };
});

export function setLanguage(lang) {
  if (translations[lang]) {
    currentLanguage.set(lang);
  }
}