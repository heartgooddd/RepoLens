import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const proxy = { '/api': { target: process.env.REPOLENS_API_PROXY || 'http://127.0.0.1:8000', changeOrigin: true } }
export default defineConfig({ plugins: [react()], server: { proxy }, preview: { proxy } })
