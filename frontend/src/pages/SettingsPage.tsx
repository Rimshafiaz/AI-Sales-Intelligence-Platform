import { useEffect, useState } from 'react'
import { Mail } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { Notice } from '../components/ui'
import { api } from '../lib/api'
import type { GmailAuthorization, GmailConnection } from '../lib/types'


export default function SettingsPage() {
  const [searchParams] = useSearchParams()
  const [connection, setConnection] = useState<GmailConnection | null>(null)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    api<GmailConnection>('/integrations/gmail')
      .then((data) => {
        if (active) setConnection(data)
      })
      .catch((requestError: unknown) => {
        if (active) setError(requestError instanceof Error ? requestError.message : 'Could not load integrations.')
      })
    return () => {
      active = false
    }
  }, [])

  async function connect() {
    setWorking(true)
    setError(null)
    try {
      const result = await api<GmailAuthorization>('/integrations/gmail/connect', { method: 'POST' })
      window.location.assign(result.authorization_url)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Could not start Gmail connection.')
      setWorking(false)
    }
  }

  async function disconnect() {
    setWorking(true)
    setError(null)
    try {
      await api('/integrations/gmail', { method: 'DELETE' })
      setConnection((current) => current ? { ...current, status: 'disconnected' } : current)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Could not disconnect Gmail.')
    } finally {
      setWorking(false)
    }
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <p className="label-caps text-secondary">Settings</p>
      <h1 className="mt-1 font-display text-headline-xl font-semibold text-on-surface">Integrations</h1>
      <p className="mt-2 text-body-md text-on-surface-variant">Connect accounts used for approved SalesLens actions.</p>

      <div className="mt-6 space-y-3">
        {searchParams.get('gmail') === 'connected' && <Notice kind="info">Gmail connected successfully.</Notice>}
        {searchParams.get('gmail') === 'error' && <Notice kind="error">Gmail connection was not completed. Please try again.</Notice>}
        {error && <Notice kind="error">{error}</Notice>}
      </div>

      <section className="mt-6 rounded-card border border-line-soft bg-surface-container-lowest p-5 shadow-sm">
        <div className="flex items-start gap-4">
          <Mail className="mt-1 shrink-0 text-secondary" size={22} />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-display text-headline-md font-semibold text-on-surface">Gmail</h2>
                <p className="mt-1 text-body-sm text-on-surface-variant">SalesLens requests permission to send only emails you explicitly approve.</p>
              </div>
              {connection?.status === 'connected' ? (
                <button type="button" disabled={working} onClick={() => void disconnect()} className="rounded-control border border-line px-3 py-2 text-label-md font-medium text-on-surface disabled:opacity-60">Disconnect</button>
              ) : (
                <button type="button" disabled={working || connection?.configured === false} onClick={() => void connect()} className="rounded-control bg-primary px-3 py-2 text-label-md font-medium text-on-primary disabled:opacity-60">Connect Gmail</button>
              )}
            </div>
            {connection?.status === 'connected' && <p className="mt-3 text-body-sm text-on-surface">Connected as {connection.email}</p>}
            {connection?.configured === false && <p className="mt-3 text-body-sm text-error">Gmail OAuth has not been configured on this SalesLens server.</p>}
            <p className="mt-3 text-label-sm text-on-surface-variant">M83 connects the account only. It does not send email. Sending is added in M84.</p>
          </div>
        </div>
      </section>
    </main>
  )
}
