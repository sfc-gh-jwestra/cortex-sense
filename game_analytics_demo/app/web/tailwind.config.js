/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bon: "#29b5e8",
        baseline: "#64748b",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};
