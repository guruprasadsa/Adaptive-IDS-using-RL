import react from '@vitejs/plugin-react';
import path from 'path';
import { defineConfig, loadEnv } from 'vite';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, '.', '');
    
    return {
      plugins: [react()],
      
      // Environment variables are automatically exposed if prefixed with VITE_
      // No need to manually define them
      define: {
        // Legacy support for non-VITE prefixed env vars
        'process.env.API_KEY': JSON.stringify(env.GEMINI_API_KEY),
        'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY)
      },
      
      resolve: {
        alias: {
          '@': path.resolve(__dirname, '.'),
        },
        extensions: ['.ts', '.tsx', '.js', '.jsx', '.json']
      },

      // Server configuration for development
      server: {
        port: 5173,
        strictPort: false,
        host: '0.0.0.0',
        proxy: {
          // Proxy API requests during development to avoid CORS
          '/api': {
            target: env.VITE_API_BASE_URL || 'http://localhost:5001',
            changeOrigin: true,
            secure: false,
          }
        }
      },

      // Build configuration - optimized for production
      build: {
        outDir: 'dist',
        sourcemap: mode === 'development',
        minify: 'esbuild', // Use esbuild (default, faster than terser)
        target: 'es2020', // ES2020 supports top-level await
        // Optimize chunks for better caching
        rollupOptions: {
          output: {
            manualChunks: {
              'vendor': ['react', 'react-dom'],
              'query': ['@tanstack/react-query'],
              'charts': ['chart.js'],
              'utils': ['axios'],
            },
            // Optimize chunk names for better caching
            chunkFileNames: 'assets/[name]-[hash].js',
            entryFileNames: 'assets/[name]-[hash].js',
            assetFileNames: 'assets/[name]-[hash].[ext]',
          },
          // Tree shaking optimization
          treeshake: {
            moduleSideEffects: false,
          },
        },
        // Increase chunk size warning limit
        chunkSizeWarningLimit: 1000,
        // Enable CSS code splitting
        cssCodeSplit: true,
      },

      // Enable CSS source maps in development
      css: {
        devSourcemap: mode === 'development'
      }
    };
});
