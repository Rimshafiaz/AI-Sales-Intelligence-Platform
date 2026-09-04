import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
// Display font: Manrope for headings, titles, logo, big metrics
import '@fontsource/manrope/600.css'
import '@fontsource/manrope/700.css'
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/libre-baskerville/400.css'
import '@fontsource/libre-baskerville/400-italic.css'
import '@fontsource/libre-baskerville/700.css'
import './index.css'
import App from './App'
import { AuthProvider } from './lib/auth'

// DEV font explorer — append ?font=<family> to the URL to preview any
// Google Font live, e.g. ?font=figtree, ?font=inter, ?font=public-sans,
// ?font=ibm-plex-sans, ?font=source-sans-3, ?font=manrope, ?font=dm-sans,
// ?font=work-sans, ?font=karla, ?font=outfit, ?font=rubik.
// Remove this block once the final font is chosen.
if (import.meta.env.DEV) {
  const family = new URLSearchParams(window.location.search).get('font')
  if (family) {
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.href = `https://fonts.googleapis.com/css2?family=${family}:wght@400;500;600;700&display=swap`
    document.head.appendChild(link)
    document.documentElement.style.setProperty(
      '--font-app',
      `'${family.replace(/-/g, ' ')}', system-ui, sans-serif`,
    )
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
