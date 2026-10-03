export const config = {
  apiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000',
  requestTimeoutMs: 15000,
  maxAudioDurationSeconds: 90,
  maxImageSizeMb: 8
} as const;
