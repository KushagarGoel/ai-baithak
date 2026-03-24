export const PERSONAS: Record<string, { name: string; description: string }> = {
  the_lazy_one: {
    name: 'The Lazy One',
    description: 'Finds the easiest, quickest solutions',
  },
  the_egomaniac: {
    name: 'The Know-It-All',
    description: 'Confident and knowledgeable but arrogant',
  },
  the_devils_advocate: {
    name: "Devil's Advocate",
    description: 'Challenges assumptions and finds flaws',
  },
  the_creative: {
    name: 'The Creative',
    description: 'Thinks outside the box',
  },
  the_pragmatist: {
    name: 'The Pragmatist',
    description: 'Focused on what actually works',
  },
  the_empath: {
    name: 'The Empath',
    description: 'Emotionally intelligent and human-focused',
  },
  the_researcher: {
    name: 'The Researcher',
    description: 'Evidence-based and thorough',
  },
};

export function getPersonaDisplayName(key: string): string {
  return PERSONAS[key]?.name || key;
}

export function getPersonaDescription(key: string): string {
  return PERSONAS[key]?.description || '';
}

export function getPersonaOptions() {
  return Object.entries(PERSONAS).map(([key, { name }]) => ({
    value: key,
    label: name,
  }));
}
