import { useCallback, useEffect, useState } from 'react'

import {
  WEB_PUSH_STATUS,
  WEB_PUSH_STATUS_LABELS,
  deriveInitialWebPushStatus,
} from './fcmConfig.js'
import {
  disableBrowserPush,
  enableBrowserPush,
  isBrowserPushSupported,
  isWebPushConfigured,
  readStoredFcmRegistration,
  syncExistingBrowserPush,
} from './fcmClient.js'

/**
 * INT03-R2: React hook managing the explicit "Bật thông báo trên trình duyệt" lifecycle.
 * Never prompts Notification.requestPermission() automatically.
 */
export function useWebPush(userId) {
  const configured = isWebPushConfigured()
  const [status, setStatus] = useState(() =>
    configured ? WEB_PUSH_STATUS.DISABLED : WEB_PUSH_STATUS.UNCONFIGURED,
  )
  const [detail, setDetail] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let active = true
    async function init() {
      const supported = await isBrowserPushSupported()
      if (!active) return
      const permission = typeof Notification !== 'undefined' ? Notification.permission : 'default'
      const stored = readStoredFcmRegistration()
      const next = deriveInitialWebPushStatus({
        configured,
        supported,
        permission,
        registeredUserId: stored?.userId || null,
        currentUserId: userId || null,
      })
      setStatus(next)
      if (next === WEB_PUSH_STATUS.ENABLED && userId) {
        syncExistingBrowserPush(userId)
      }
    }
    init()
    return () => {
      active = false
    }
  }, [configured, userId])

  const enable = useCallback(async () => {
    setBusy(true)
    setDetail(null)
    setStatus(WEB_PUSH_STATUS.REGISTERING)
    const res = await enableBrowserPush(userId)
    setStatus(res.status)
    setDetail(res.message || null)
    setBusy(false)
    return res
  }, [userId])

  const disable = useCallback(async () => {
    setBusy(true)
    setDetail(null)
    const res = await disableBrowserPush()
    setStatus(res.status)
    setBusy(false)
    return res
  }, [])

  return {
    status,
    statusLabel: WEB_PUSH_STATUS_LABELS[status] || status,
    detail,
    busy,
    configured,
    canEnable:
      !busy &&
      Boolean(userId) &&
      (status === WEB_PUSH_STATUS.DISABLED || status === WEB_PUSH_STATUS.UNAVAILABLE),
    canDisable: !busy && status === WEB_PUSH_STATUS.ENABLED,
    enable,
    disable,
  }
}

export default useWebPush
