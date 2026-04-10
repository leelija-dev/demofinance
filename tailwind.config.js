/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./headquater/templates/**/*.html",
    "./agent/templates/**/*.html",
    "./branch/templates/**/*.html",
    "./loan/templates/**/*.html",
    "./static/js/**/*.js",
    "./node_modules/flowbite/**/*.js",
    "templates/*.html",
  ],
  darkMode: "class",
  important: false, // Add this to ensure Tailwind styles take precedence
  corePlugins: {
    preflight: true, // Disable preflight to avoid conflicts with existing styles
  },
  theme: {
    screens: {
      smx:"365px",
      xs: "475px",
      sm: "640px",
      md: "768px",
      slg: "991px",
      lg: "1024px",
      xl: "1280px",
      xll: "1368px",
      "2xl": "1536px",
    },
    extend: {
      fontSize: {
        // Heading 1
        // Heading 1
        "h1-xs": ["1.75rem", { lineHeight: "1.2" }],
        "h1-sm": ["2.25rem", { lineHeight: "1.2" }],
        "h1-md": ["3rem", { lineHeight: "1.15" }],
        "h1-lg": ["2.8rem", { lineHeight: "1.15" }],
        "h1-lgg": ["3rem", { lineHeight: "1.15" }],
        "h1-xl": ["3.2rem", { lineHeight: "1.15" }],
        "h1-2xl": ["4rem", { lineHeight: "1.15" }],

        // Heading 2
        "h2-xs": ["1.5rem", { lineHeight: "1.25" }],
        "h2-sm": ["1.75rem", { lineHeight: "1.25" }],
        "h2-md": ["2rem", { lineHeight: "1.2" }],
        "h2-lg": ["2.25rem", { lineHeight: "1.2" }],
        "h2-lgg": ["2.3rem", { lineHeight: "1.1" }],
        "h2-xl": ["2.5rem", { lineHeight: "1.25" }],
        "h2-2xl": ["3rem", { lineHeight: "1.25" }],

        // Heading 3
        "h3-xs": ["1.25rem", { lineHeight: "1.3" }],
        "h3-sm": ["1.5rem", { lineHeight: "1.3" }],
        "h3-md": ["1.75rem", { lineHeight: "1.25" }],
        "h3-lg": ["1.75rem", { lineHeight: "1.25" }],
        "h3-lgg": ["1.85rem", { lineHeight: "1.2" }],
        "h3-xl": ["2rem", { lineHeight: "1.2" }],
        "h3-2xl": ["2.4rem", { lineHeight: "1.1" }],

        // Heading 4
        "h4-xs": ["1.125rem", { lineHeight: "1.4" }],
        "h4-sm": ["1.25rem", { lineHeight: "1.4" }],
        "h4-md": ["1.5rem", { lineHeight: "1.3" }],
        "h4-lg": ["1.75rem", { lineHeight: "1.3" }],
        "h4-lgg": ["1.875rem", { lineHeight: "1.25" }],
        "h4-xl": ["2rem", { lineHeight: "1.25" }],
        "h4-2xl": ["2.25rem", { lineHeight: "1.2" }],

        //heading 5
        "h5-xs": ["1.rem", { lineHeight: "1.4" }],
        "h5-sm": ["1.rem", { lineHeight: "1.4" }],
        "h5-md": ["1.125rem", { lineHeight: "1.3" }],
        "h5-lg": ["1.25rem", { lineHeight: "1.3" }],
        "h5-lgg": ["1.5rem", { lineHeight: "1.25" }],
        "h5-xl": ["1.625rem", { lineHeight: "1.25" }],
        "h5-2xl": ["1.7rem", { lineHeight: "1.2" }],

        // Paragraph
        "p-xs": ["0.875rem", { lineHeight: "1.5" }],
        "p-sm": ["1rem", { lineHeight: "1.5" }],
        "p-md": ["1.025rem", { lineHeight: "1.5" }],
        "p-lg": ["1.050rem", { lineHeight: "1.5" }],
        "p-lgg": ["1rem", { lineHeight: "1.5" }],
        "p-xl": ["1.2rem", { lineHeight: "1.5" }],
        "p-2xl": ["1.325rem", { lineHeight: "1.4" }],

        // Small Text (span, li, etc.)
        "text-xs": ["0.75rem", { lineHeight: "1.5" }],
        "text-sm": ["0.875rem", { lineHeight: "1.5" }],
        "text-md": ["1rem", { lineHeight: "1.5" }],
        "text-lg": ["1.125rem", { lineHeight: "1.5" }],
        "text-lgg": ["1.25rem", { lineHeight: "1.4" }],
        "text-xl": ["1.375rem", { lineHeight: "1.4" }],
        "text-2xl": ["1.5rem", { lineHeight: "1.3" }],

        // Links (can use same as paragraph or smaller)
        "a-xs": ["0.875rem", { lineHeight: "1.5" }],
        "a-sm": ["1rem", { lineHeight: "1.5" }],
        "a-md": ["1.125rem", { lineHeight: "1.5" }],
        // ... continue pattern as needed
      },
      colors: {
        primary: {
          DEFAULT: "#3C50E0",
          dark: "#1E40AF",
        },
        secondary: {
          DEFAULT: "#10B981",
          dark: "#059669",
        },
        dark: {
          DEFAULT: "#1E293B",
          light: "#334155",
          lighter: "#475569",
        },
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
      },
      spacing: {
        sidebar: "290px",
        "sidebar-collapsed": "90px",
      },
      transitionProperty: {
        width: "width",
        spacing: "margin, padding",
      },
    },
  },
  plugins: [require("@tailwindcss/forms"), require("@tailwindcss/typography")],
};
