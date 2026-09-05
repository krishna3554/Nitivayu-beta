/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        // Inter is the workhorse. Favorit (licensed) is substituted with the
        // same Inter stack tuned with +0.56px tracking — see .font-nav/.font-caption.
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        nav: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
      },
      fontWeight: {
        // DESIGN.md allows exactly 400 / 500 / 550 / 700. No 600, no 300.
        normal: '400',
        medium: '500',
        'medium-plus': '550',
        bold: '700',
      },
      colors: {
        // Fireworks tokens — single accent system. Violet is the only CTA color.
        primary: {
          DEFAULT: '#6720FF',
          subtle: '#E0D1FF',
        },
        interactive: '#1863DC',
        ink: {
          DEFAULT: '#000000',
          secondary: '#212121',
        },
        surface: {
          white: '#FFFFFF',
          muted: '#F4F4F4',
        },
        border: '#E6EAF4',
        // Status colors (from nitivayu.md §2.1, scoped to status/severity only —
        // never as page chrome, to preserve the black/white/violet hierarchy).
        success: '#059669',
        pending: '#F59E0B',
        critical: '#E11D48',
        academic: '#4F46E5',
        csr: '#0284C7',
      },
      borderRadius: {
        // Only two radii exist. Do not introduce pills or larger corners.
        sm: '2px',
        md: '8px',
      },
      spacing: {
        // 9-step scale; space-2 (8px) and space-6 (28px) are the workhorses.
        'space-1': '4px',
        'space-2': '8px',
        'space-3': '12px',
        'space-4': '16px',
        'space-5': '24px',
        'space-6': '28px',
        'space-7': '32px',
        'space-8': '40px',
        'space-9': '64px',
      },
      boxShadow: {
        // The only sanctioned shadow: faint upward glow on cards. No drop shadows.
        card: 'rgba(172, 171, 171, 0.3) 0px -1px 10px 0px',
      },
      maxWidth: {
        content: '76rem',
      },
    },
  },
  plugins: [],
}
