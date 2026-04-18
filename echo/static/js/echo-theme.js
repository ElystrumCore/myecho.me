/**
 * Echo Adaptive Theme
 *
 * Adapted from VSMarket's AE-FHS-068 adaptive UI system.
 * Instead of UTM→persona→theme, Echo uses content→register→atmosphere.
 *
 * The voice has registers. The UI should match.
 * - "signal" (default): deep dark, orange accent — the thinking room
 * - "field": warmer tones, earth accent — the construction voice
 * - "technical": midnight blue, cool — the architecture voice
 * - "light": clean, readable — the public-facing voice
 */

const ECHO_THEMES = {
  signal: {
    name: 'Signal',
    description: 'The thinking room',
    vars: {
      '--bg': '#0d0d0f',
      '--surface': '#141417',
      '--text': '#f0ede8',
      '--text-muted': '#6b6b73',
      '--accent': '#e8622a',
      '--accent-glow': 'rgba(232, 98, 42, 0.04)',
      '--border': 'rgba(255, 255, 255, 0.08)',
    }
  },
  field: {
    name: 'Field',
    description: 'Boots on the ground',
    vars: {
      '--bg': '#0f0e0c',
      '--surface': '#171613',
      '--text': '#ede8df',
      '--text-muted': '#7a7568',
      '--accent': '#c4883a',
      '--accent-glow': 'rgba(196, 136, 58, 0.04)',
      '--border': 'rgba(255, 255, 255, 0.07)',
    }
  },
  technical: {
    name: 'Technical',
    description: 'Deep architecture',
    vars: {
      '--bg': '#0a0e17',
      '--surface': '#111827',
      '--text': '#e5e7eb',
      '--text-muted': '#6b7280',
      '--accent': '#3b82f6',
      '--accent-glow': 'rgba(59, 130, 246, 0.04)',
      '--border': 'rgba(59, 130, 246, 0.1)',
    }
  },
  light: {
    name: 'Light',
    description: 'Public voice',
    vars: {
      '--bg': '#fafaf8',
      '--surface': '#ffffff',
      '--text': '#1a1a1a',
      '--text-muted': '#6b6b73',
      '--accent': '#c4501a',
      '--accent-glow': 'rgba(196, 80, 26, 0.03)',
      '--border': 'rgba(0, 0, 0, 0.08)',
    }
  },
};

class EchoThemeManager {
  constructor() {
    this.currentTheme = localStorage.getItem('echo-theme') || 'signal';
    this.listeners = [];
    this.apply(this.currentTheme);

    // System preference detection
    if (window.matchMedia) {
      const mq = window.matchMedia('(prefers-color-scheme: light)');
      mq.addEventListener('change', (e) => {
        if (this.currentTheme === 'auto') {
          this.apply(e.matches ? 'light' : 'signal');
        }
      });
    }

    // Keyboard shortcut: Ctrl/Cmd + Shift + T
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'T') {
        e.preventDefault();
        this.cycle();
      }
    });
  }

  apply(theme) {
    const config = ECHO_THEMES[theme];
    if (!config) return;

    const root = document.documentElement;

    // Transition
    root.style.transition = 'background-color 0.3s, color 0.3s';

    Object.entries(config.vars).forEach(([prop, value]) => {
      root.style.setProperty(prop, value);
    });

    root.setAttribute('data-echo-theme', theme);
    this.currentTheme = theme;
    localStorage.setItem('echo-theme', theme);

    // Notify listeners
    this.listeners.forEach(fn => fn(theme));

    // Clean up transition
    setTimeout(() => {
      root.style.transition = '';
    }, 350);
  }

  cycle() {
    const themes = Object.keys(ECHO_THEMES);
    const idx = themes.indexOf(this.currentTheme);
    const next = themes[(idx + 1) % themes.length];
    this.apply(next);

    // Show brief toast
    this.showToast(`${ECHO_THEMES[next].name} — ${ECHO_THEMES[next].description}`);
  }

  onChange(fn) {
    this.listeners.push(fn);
  }

  showToast(message) {
    const existing = document.querySelector('.echo-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'echo-toast';
    toast.textContent = message;
    toast.style.cssText = `
      position: fixed; bottom: 2rem; right: 2rem;
      background: var(--surface); color: var(--text-muted);
      padding: 0.5rem 1rem; border-radius: 6px;
      font-size: 12px; font-family: var(--font-mono);
      border: 1px solid var(--border);
      opacity: 0; transition: opacity 0.2s;
      z-index: 1000;
    `;
    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.style.opacity = '1');
    setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 200);
    }, 1500);
  }
}

// Auto-initialize
window.echoTheme = new EchoThemeManager();
