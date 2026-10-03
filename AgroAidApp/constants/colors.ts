export const colors = {
  brand: {
    primary: '#2F7D32',
    secondary: '#86A83E',
    accent: '#DFA53A'
  },
  risk: {
    low: '#2F7D32',
    medium: '#DFA53A',
    high: '#D96C2C',
    critical: '#B42318'
  },
  surface: {
    background: '#F7FBF3',
    card: '#FFFFFF',
    border: '#D9E4D0',
    muted: '#EEF5E8'
  },
  text: {
    primary: '#162316',
    secondary: '#52634D',
    inverse: '#FFFFFF'
  }
} as const;

export type AppColors = typeof colors;
