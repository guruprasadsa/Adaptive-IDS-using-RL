import path from 'path';
import { defineConfig, loadEnv } from 'vite';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, '.', '');
    
    return {
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
        }
      },

      // Server configuration for development
      server: {
        port: 5173,
        strictPort: false,
        proxy: {
          // Optional: proxy API requests during development
          // Uncomment if you want to use relative URLs instead of absolute
          // '/api': {
          //   target: env.VITE_API_BASE_URL || 'http://localhost:5000',
          //   changeOrigin: true,
          // }
        }
      },

      // Build configuration
      build: {
        outDir: 'dist',
        sourcemap: mode === 'development',
        // Optimize chunks
        rollupOptions: {
          output: {
            manualChunks: {
              'vendor': ['axios', '@tanstack/react-query'],
              'charts': ['chart.js'],
            }
          }
        }
      },

      // Enable CSS source maps in development
      css: {
        devSourcemap: mode === 'development'
      }
    };
});
