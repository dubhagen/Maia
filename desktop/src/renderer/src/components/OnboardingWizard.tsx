import React, { useEffect, useMemo, useState } from 'react'
import { KeyRound, Loader2, ArrowRight } from 'lucide-react'
import { t } from '../i18n'
import apiClient from '../api/client'
import type { ModelsData } from '../types'
import { Field, Dropdown, TextInput, type DropdownOption } from '../pages/settings/primitives'
import { resolveModels, providerLabel } from '../pages/settings/modelsHelpers'
import { useOnboardingStore } from '../store/onboardingStore'

interface OnboardingWizardProps {
  // Called after the wizard finishes so the host can refresh language/state.
  onDone: () => void
}

const TOTAL_STEPS = 1

// First-run guided setup: LiteLLM base, key, and chat model.
// Rendered as a full-screen overlay above the main UI.
const OnboardingWizard: React.FC<OnboardingWizardProps> = ({ onDone }) => {
  const finish = useOnboardingStore((s) => s.finish)

  const [step] = useState(1)
  const [models, setModels] = useState<ModelsData | null>(null)
  const [discovered, setDiscovered] = useState<string[]>([])

  // Step 2 form state.
  const [provider, setProvider] = useState('litellm')
  const [apiKey, setApiKey] = useState('')
  const [apiBase, setApiBase] = useState('')
  const [model, setModel] = useState('')

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  // Load the models console data once for the provider/model dropdowns.
  useEffect(() => {
    apiClient
      .getModels()
      .then((data) => {
        setModels(data)
        const id = (data?.capabilities?.chat?.providers || [])[0] || 'litellm'
        setProvider(id)
        const meta = data?.providers?.find((p) => p.id === id)
        if (meta?.api_base) setApiBase(meta.api_base)
        else if (meta?.api_base_default) setApiBase(meta.api_base_default)
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
  }, [])

  // Ask the proxy for its model list as soon as a base (and optional key) is typed.
  useEffect(() => {
    const base = apiBase.trim().replace(/\/$/, '')
    if (!/^https?:\/\/.+\/v1$/.test(base)) return
    const handle = window.setTimeout(() => {
      apiClient.modelsAction({
        action: 'discover_models',
        provider_id: provider || 'litellm',
        api_base: base,
        ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}),
      }).then((res) => {
        if (res.status !== 'success') {
          setDiscovered([])
          const message = typeof res.message === 'string' ? res.message : ''
          // An empty key against a locked proxy is expected until the user pastes one.
          if (apiKey.trim() || !/HTTP 40[13]/.test(message)) {
            setError(message || t('onboarding_save_failed'))
          }
          return
        }
        const rows = Array.isArray(res.models) ? res.models : []
        const names = rows
          .map((item) => (item && typeof item === 'object' ? item as Record<string, unknown> : null))
          .filter((item): item is Record<string, unknown> => !!item)
          .filter((item) => {
            const caps = item.capabilities
            return Array.isArray(caps) && caps.includes('text')
          })
          .map((item) => String(item.name || '').trim())
          .filter(Boolean)
        setDiscovered(names)
        setError('')
        setModel((current) => current || names[0] || '')
      }).catch((err) => {
        setDiscovered([])
        setError(err instanceof Error ? err.message : String(err))
      })
    }, 400)
    return () => window.clearTimeout(handle)
  }, [apiKey, apiBase, provider])

  const providerOptions: DropdownOption[] = useMemo(() => {
    const chat = models?.capabilities?.chat
    const ids = chat?.providers || []
    return ids.map((id) => ({ value: id, label: providerLabel(models, id) }))
  }, [models])

  const modelOptions: DropdownOption[] = useMemo(() => {
    return resolveModels(models, provider, models?.capabilities?.chat?.provider_models).map((o) => ({
      value: o.value,
      label: o.value,
      hint: o.hint,
    }))
  }, [models, provider])

  // The currently selected provider's api_base placeholder/default, if any.
  const providerMeta = models?.providers?.find((p) => p.id === provider)
  const apiBasePlaceholder = providerMeta?.api_base_placeholder || providerMeta?.api_base_default

  const handleProvider = (id: string) => {
    setProvider(id)
    setApiBase('')
    const first = resolveModels(models, id, models?.capabilities?.chat?.provider_models)[0]
    setModel(first?.value || '')
  }

  // A LiteLLM /v1 base and a model id. The proxy key may be empty.
  const baseOk = /^https?:\/\/.+\/v1\/?$/.test(apiBase.trim())
  const canNext = !!provider && baseOk && !!model.trim()

  const goNext = async () => {
    setError('')
    // Step 2 is the last step: persist the provider credentials, point the chat
    // capability at it, then finish straight into the chat (no extra step).
    setSaving(true)
    try {
      const saved = await apiClient.modelsAction({
        action: 'set_provider',
        provider_id: provider,
        ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}),
        api_base: apiBase.trim().replace(/\/$/, ''),
      })
      if (saved.status !== 'success') {
        setSaving(false)
        setError(typeof saved.message === 'string' ? saved.message : t('onboarding_save_failed'))
        return
      }
      const picked = await apiClient.modelsAction({
        action: 'set_capability',
        capability: 'chat',
        provider_id: provider,
        model,
      })
      if (picked.status !== 'success') {
        setSaving(false)
        setError(typeof picked.message === 'string' ? picked.message : t('onboarding_save_failed'))
        return
      }
    } catch (err) {
      setSaving(false)
      setError(err instanceof Error ? err.message : t('onboarding_save_failed'))
      return
    }
    setSaving(false)
    complete()
  }

  const complete = () => {
    finish()
    onDone()
  }

  const stepLabel = t('onboarding_step').replace('{n}', String(step)).replace('{total}', String(TOTAL_STEPS))

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-base">
      <div className="w-full max-w-lg px-8">
        {/* Progress dots */}
        <div className="flex items-center justify-center gap-2 mb-8">
          {Array.from({ length: TOTAL_STEPS }).map((_, i) => (
            <span
              key={i}
              className={`h-1.5 rounded-full transition-all ${
                i + 1 === step ? 'w-8 bg-accent' : i + 1 < step ? 'w-4 bg-accent/50' : 'w-4 bg-surface-2'
              }`}
            />
          ))}
        </div>

        {step === 1 && (
          <div className="space-y-6">
            <div className="text-center space-y-2">
              <div className="w-16 h-16 rounded-2xl bg-accent-soft text-accent flex items-center justify-center mx-auto">
                <KeyRound size={28} />
              </div>
              <h1 className="text-2xl font-bold text-content">{t('onboarding_model_title')}</h1>
              <p className="text-sm text-content-secondary">{t('onboarding_model_desc')}</p>
            </div>
            <div className="space-y-4">
              <Field label={t('onboarding_provider')}>
                <Dropdown
                  value={provider}
                  options={providerOptions}
                  placeholder={t('onboarding_select_provider')}
                  onChange={handleProvider}
                />
              </Field>
              {provider && (
                <>
                  <Field label={t('onboarding_apikey')}>
                    <TextInput
                      type="password"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder={t('onboarding_apikey_placeholder')}
                      className="font-mono"
                    />
                  </Field>
                  <Field label={t('onboarding_apibase')}>
                    <TextInput
                      value={apiBase}
                      onChange={(e) => setApiBase(e.target.value)}
                      placeholder={apiBasePlaceholder || 'http://127.0.0.1:4000/v1'}
                      className="font-mono"
                    />
                  </Field>
                  <Field label={t('onboarding_model')}>
                    {discovered.length ? (
                      <Dropdown
                        value={model}
                        options={discovered.map((name) => ({ value: name, label: name }))}
                        placeholder={t('onboarding_select_model')}
                        onChange={setModel}
                      />
                    ) : (
                      <TextInput
                        value={model}
                        onChange={(e) => setModel(e.target.value)}
                        placeholder={modelOptions[0]?.value || t('onboarding_select_model')}
                        className="font-mono"
                      />
                    )}
                  </Field>
                </>
              )}
              {error && <p className="text-sm text-danger">{error}</p>}
            </div>
          </div>
        )}

        {/* Footer controls */}
        <div className="mt-10 flex items-center justify-between">
          <div className="text-xs text-content-tertiary">{stepLabel}</div>
          <div className="flex items-center gap-2">
            {/* Skip dismisses the wizard and goes straight to chat. */}
            <button
              onClick={complete}
              disabled={saving}
              className="px-4 py-2 rounded-btn text-sm font-medium text-content-tertiary hover:text-content cursor-pointer transition-colors disabled:opacity-50"
            >
              {t('onboarding_skip')}
            </button>
            {/* Primary action: advance on step 1, save + finish on the last step. */}
            <button
              onClick={goNext}
              disabled={!canNext || saving}
              className="px-5 py-2 rounded-btn bg-accent text-accent-contrast hover:bg-accent-hover text-sm font-medium cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-1.5"
            >
              {saving && <Loader2 size={15} className="animate-spin" />}
              {saving
                ? t('onboarding_saving')
                : step === TOTAL_STEPS
                  ? t('onboarding_finish')
                  : t('onboarding_next')}
              {!saving && <ArrowRight size={15} />}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default OnboardingWizard
