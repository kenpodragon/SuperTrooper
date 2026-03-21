import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteStaticCopy } from "vite-plugin-static-copy";
import { resolve } from "path";

// Chrome extension content scripts cannot use ES module imports.
// We build content + background as self-contained IIFE bundles via
// separate Vite build passes, and popup as a normal SPA.
export default defineConfig(({ mode }) => {
  const target = mode; // "content", "background", or "production" (popup)

  // Content script build — IIFE, no code splitting
  if (target === "content") {
    return {
      build: {
        outDir: "dist",
        emptyOutDir: false,
        lib: {
          entry: resolve(__dirname, "src/content/index.ts"),
          name: "SuperTroopersContent",
          formats: ["iife"],
          fileName: () => "content.js",
        },
        rollupOptions: {
          output: { extend: true },
        },
      },
      resolve: {
        alias: {
          "@shared": resolve(__dirname, "src/shared"),
          "@config": resolve(__dirname, "src/config"),
        },
      },
    };
  }

  // Background service worker build — IIFE, no code splitting
  if (target === "background") {
    return {
      build: {
        outDir: "dist",
        emptyOutDir: false,
        lib: {
          entry: resolve(__dirname, "src/background/index.ts"),
          name: "SuperTroopersBackground",
          formats: ["iife"],
          fileName: () => "background.js",
        },
        rollupOptions: {
          output: { extend: true },
        },
      },
      resolve: {
        alias: {
          "@shared": resolve(__dirname, "src/shared"),
          "@config": resolve(__dirname, "src/config"),
        },
      },
    };
  }

  // Default: popup SPA + static assets
  return {
    plugins: [
      react(),
      viteStaticCopy({
        targets: [
          { src: "manifest.json", dest: "." },
          { src: "assets/**/*", dest: "assets" },
        ],
      }),
    ],
    build: {
      outDir: "dist",
      emptyOutDir: true,
      rollupOptions: {
        input: {
          popup: resolve(__dirname, "src/popup/index.html"),
        },
        output: {
          entryFileNames: "[name].js",
          assetFileNames: "assets/[name][extname]",
        },
      },
    },
    resolve: {
      alias: {
        "@shared": resolve(__dirname, "src/shared"),
        "@config": resolve(__dirname, "src/config"),
      },
    },
  };
});
