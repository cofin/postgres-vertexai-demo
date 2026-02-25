/**
 * Theme Toggle System
 * 
 * Manages dark/light mode switching with persistence.
 * Dark mode is the default, light mode can be enabled.
 * 
 * Usage:
 * - Add to HTML: <script src="{{ url_for('static', file_path='js/theme-toggle.js') }}"></script>
 * - Toggle button: <button onclick="toggleTheme()" id="theme-toggle">...</button>
 */

(function() {
  'use strict';

  const STORAGE_KEY = 'cymbal-theme-preference';
  const DARK_CLASS = 'dark';
  
  /**
   * Get the current theme preference.
   * Priority: 1. localStorage, 2. system preference, 3. dark (default)
   */
  function getThemePreference() {
    // Check localStorage first
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      return stored;
    }
    
    // Check system preference
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
      return 'light';
    }
    
    // Default to dark
    return 'dark';
  }

  /**
   * Apply the theme to the document.
   */
  function applyTheme(theme) {
    const root = document.documentElement;
    
    if (theme === 'light') {
      root.setAttribute('data-theme', 'light');
      root.classList.remove(DARK_CLASS);
    } else {
      root.setAttribute('data-theme', 'dark');
      root.classList.add(DARK_CLASS);
    }
    
    // Update toggle button icon if it exists
    updateToggleIcon(theme);
  }

  /**
   * Update the toggle button icon.
   */
  function updateToggleIcon(theme) {
    const toggle = document.getElementById('theme-toggle');
    if (!toggle) return;
    
    const isDark = theme === 'dark';
    
    // Set aria-pressed for accessibility
    toggle.setAttribute('aria-pressed', isDark ? 'true' : 'false');
    
    // Update icon (SVG)
    toggle.innerHTML = isDark ? getMoonIcon() : getSunIcon();
    toggle.setAttribute('title', isDark ? 'Switch to light mode' : 'Switch to dark mode');
  }

  /**
   * Get moon SVG icon.
   */
  function getMoonIcon() {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"></path>
    </svg>`;
  }

  /**
   * Get sun SVG icon.
   */
  function getSunIcon() {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="4"></circle>
      <path d="M12 2v2"></path>
      <path d="M12 20v2"></path>
      <path d="m4.93 4.93 1.41 1.41"></path>
      <path d="m17.66 17.66 1.41 1.41"></path>
      <path d="M2 12h2"></path>
      <path d="M20 12h2"></path>
      <path d="m6.34 17.66-1.41 1.41"></path>
      <path d="m19.07 4.93-1.41 1.41"></path>
    </svg>`;
  }

  /**
   * Toggle between dark and light themes.
   */
  function toggleTheme() {
    const current = getThemePreference();
    const next = current === 'dark' ? 'light' : 'dark';
    
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
    
    // Dispatch event for other components
    window.dispatchEvent(new CustomEvent('themechange', { detail: { theme: next } }));
  }

  /**
   * Initialize theme on page load.
   */
  function initTheme() {
    const theme = getThemePreference();
    applyTheme(theme);
    
    // Listen for system preference changes
    if (window.matchMedia) {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: light)');
      mediaQuery.addEventListener('change', (e) => {
        // Only apply if user hasn't set a preference
        if (!localStorage.getItem(STORAGE_KEY)) {
          applyTheme(e.matches ? 'light' : 'dark');
        }
      });
    }
  }

  // Make functions globally available
  window.toggleTheme = toggleTheme;
  window.getThemePreference = getThemePreference;
  window.applyTheme = applyTheme;

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTheme);
  } else {
    initTheme();
  }
})();
