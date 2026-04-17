<template>
  <router-view />
  <ToastContainer />
</template>

<script setup>
import { ref, onMounted, provide } from 'vue'
import ToastContainer from './components/ToastContainer.vue'

const theme = ref('light')

function toggleTheme() {
  theme.value = theme.value === 'light' ? 'dark' : 'light'
  document.documentElement.setAttribute('data-theme', theme.value)
  localStorage.setItem('theme', theme.value)
}

provide('toggleTheme', toggleTheme)
provide('theme', theme)

onMounted(() => {
  const saved = localStorage.getItem('theme')
  if (saved) {
    theme.value = saved
  } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    theme.value = 'dark'
  }
  document.documentElement.setAttribute('data-theme', theme.value)
})
</script>

<style>
/* ================================
   石化助手 — Global Design Tokens
   ================================ */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=DM+Mono:wght@400;500&display=swap');

:root {
  /* Brand */
  --color-primary: #2563eb;
  --color-primary-hover: #1d4ed8;
  --color-primary-active: #1e40af;
  --color-primary-muted: #dbeafe;
  --color-primary-text: #1e40af;

  /* Semantic */
  --color-success: #22c55e;
  --color-success-dark: #16a34a;
  --color-success-bg: #dcfce7;
  --color-success-text: #166534;
  --color-warning-bg: #fef3c7;
  --color-warning-text: #92400e;
  --color-highlight-bg: #fde68a;
  --color-danger-bg: #fee2e2;
  --color-danger-text: #991b1b;
  --color-error: #dc2626;
  --color-error-hover: #b91c1c;

  /* Neutrals — cool gray, consistent hue */
  --color-bg: #ffffff;
  --color-surface: #f9fafb;
  --color-surface-hover: #f3f4f6;
  --color-border: #e5e7eb;
  --color-border-strong: #d1d5db;
  --color-text: #111827;
  --color-text-secondary: #4b5563;
  --color-text-muted: #6b7280;
  --color-text-faint: #9ca3af;

  /* Typography */
  --font-sans: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-mono: 'DM Mono', 'Cascadia Code', 'Consolas', monospace;

  /* Spacing */
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-5: 1.25rem;
  --space-6: 1.5rem;
  --space-8: 2rem;

  /* Radii */
  --radius-sm: 3px;
  --radius: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-xl: 12px;
  --radius-full: 9999px;

  /* Shadows */
  --shadow-sm: 0 1px 2px 0 rgba(0,0,0,0.05);
  --shadow: 0 1px 3px 0 rgba(0,0,0,0.10), 0 1px 2px -1px rgba(0,0,0,0.10);
  --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.08), 0 2px 4px -2px rgba(0,0,0,0.08);
  --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -4px rgba(0,0,0,0.08);

  /* Transitions */
  --transition-fast: 120ms ease;
  --transition: 200ms ease;
  --transition-slow: 300ms ease;

  /* Log panel */
  --log-bg: #1e1e1e;
  --log-text: #d4d4d4;
  --log-empty: #555555;
  --log-time: #666666;
  --log-info: #4fc3f7;
  --log-warning: #ffb74d;
  --log-error: #f87171;
  --log-success: #81c784;
  --log-debug: #888888;

  /* Code output */
  --output-bg: #1e1e1e;
  --output-text: #d4d4d4;

  /* Toasts */
  --toast-success-bg: #f0fdf4;
  --toast-success-text: #166534;
  --toast-success-border: #bbf7d0;
  --toast-error-bg: #fef2f2;
  --toast-error-text: #991b1b;
  --toast-error-border: #fecaca;
  --toast-info-bg: #f0f9ff;
  --toast-info-text: #0c4a6e;
  --toast-info-border: #bae6fd;
}

/* ================================
   Dark Mode (auto-detected + manual toggle)
   ================================ */
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --color-bg: #0f1117;
    --color-surface: #1a1d27;
    --color-surface-hover: #252836;
    --color-border: #2d3142;
    --color-border-strong: #3d4260;
    --color-text: #e8eaf0;
    --color-text-secondary: #a8adb8;
    --color-text-muted: #6b7280;
    --color-text-faint: #4b5563;
    --color-primary-muted: #1e3a6e;
    --color-primary-text: #93c5fd;
    --color-success-bg: #14532d;
    --color-success-text: #86efac;
    --color-warning-bg: #451a03;
    --color-warning-text: #fde68a;
    --color-danger-bg: #450a0a;
    --color-danger-text: #fca5a5;
  }
}

/* Manual dark override */
[data-theme="dark"] {
  --color-bg: #0f1117;
  --color-surface: #1a1d27;
  --color-surface-hover: #252836;
  --color-border: #2d3142;
  --color-border-strong: #3d4260;
  --color-text: #e8eaf0;
  --color-text-secondary: #a8adb8;
  --color-text-muted: #6b7280;
  --color-text-faint: #4b5563;
  --color-primary-muted: #1e3a6e;
  --color-primary-text: #93c5fd;
  --color-success-bg: #14532d;
  --color-success-text: #86efac;
  --color-warning-bg: #451a03;
  --color-warning-text: #fde68a;
  --color-danger-bg: #450a0a;
  --color-danger-text: #fca5a5;
}

/* Manual light override */
[data-theme="light"] {
  --color-bg: #ffffff;
  --color-surface: #f9fafb;
  --color-surface-hover: #f3f4f6;
  --color-border: #e5e7eb;
  --color-border-strong: #d1d5db;
  --color-text: #111827;
  --color-text-secondary: #4b5563;
  --color-text-muted: #6b7280;
  --color-text-faint: #9ca3af;
  --color-primary-muted: #dbeafe;
  --color-primary-text: #1e40af;
  --color-success-bg: #dcfce7;
  --color-success-text: #166534;
  --color-warning-bg: #fef3c7;
  --color-warning-text: #92400e;
  --color-danger-bg: #fee2e2;
  --color-danger-text: #991b1b;
}

/* ================================
   Reset & Base
   ================================ */
*, *::before, *::after {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html {
  font-size: 16px;
  scroll-behavior: smooth;
  -webkit-text-size-adjust: 100%;
}

body {
  font-family: var(--font-sans);
  font-size: 0.9375rem;
  line-height: 1.6;
  color: var(--color-text);
  background: var(--color-bg);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#app {
  min-height: 100dvh;
}

/* Typography defaults */
h1, h2, h3, h4, h5, h6 {
  font-weight: 600;
  line-height: 1.3;
  color: var(--color-text);
  letter-spacing: -0.01em;
}

a {
  color: var(--color-primary);
  text-decoration: none;
  transition: color var(--transition-fast);
}

a:hover {
  color: var(--color-primary-hover);
}

/* Focus ring — visible on keyboard nav */
:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
  border-radius: var(--radius-sm);
}

/* Selection */
::selection {
  background: var(--color-primary-muted);
  color: var(--color-primary-text);
}

/* Scrollbar */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: var(--color-border-strong);
  border-radius: var(--radius-full);
}
::-webkit-scrollbar-thumb:hover {
  background: var(--color-text-muted);
}

/* Remove default button styles */
button {
  font-family: var(--font-sans);
  cursor: pointer;
  border: none;
  background: none;
}

/* Inputs */
input, select, textarea {
  font-family: var(--font-sans);
  font-size: 0.9375rem;
}

/* Tables */
table {
  border-collapse: collapse;
  width: 100%;
}
</style>
