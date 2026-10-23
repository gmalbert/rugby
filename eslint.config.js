import globals from "globals";

export default [
  { ignores: ["node_modules/**", "dist/**", ".wrangler/**"] },
  {
    files: ["src/**/*.{js,jsx}", "worker/**/*.js", "tests/**/*.js", "*.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: { ...globals.browser, ...globals.node, ...globals.worker },
    },
    rules: {
      "no-undef": "error",
      "no-unreachable": "error",
      "no-constant-condition": "error",
      "no-duplicate-imports": "error",
    },
  },
];
