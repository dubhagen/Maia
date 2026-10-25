import React from 'react'
import { Radio } from 'lucide-react'
import { t } from '../i18n'

interface ChannelsPageProps {
  baseUrl: string
}

/** Chat is the web console. IM channel setup has been removed. */
const ChannelsPage: React.FC<ChannelsPageProps> = () => {
  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-8 space-y-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-accent-soft text-accent flex items-center justify-center">
            <Radio size={18} />
          </div>
          <div>
            <h2 className="text-xl font-bold text-content">{t('channels_title')}</h2>
            <p className="text-sm text-content-secondary">
              {t('channels_web_only')}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ChannelsPage
