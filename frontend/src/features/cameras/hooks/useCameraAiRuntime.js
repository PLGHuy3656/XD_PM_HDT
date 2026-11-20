/**
 * INT02: live AI runtime for ONE camera through the Gateway (camera ownership enforced there).
 *
 * - Polls status / latest counts / latest detections every 2s while mounted.
 * - Never invents data: 404 (no AI session yet) -> sessionState 'NONE'; 502/503/504/network ->
 *   'UNAVAILABLE'; 403 -> 'FORBIDDEN'.
 * - Webcam (LOCAL_CAMERA): browser MediaDevices -> JPEG frames at <= 4 FPS (640x480) -> Gateway
 *   -> AI pipeline. Frames are only sent while the user keeps the camera session on; tracks are
 *   stopped and the AI session is stopped when the user stops or leaves the page. Nothing is
 *   stored by the browser.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { camerasApi } from '../../../api/modules/camerasApi.js'
import { ENDPOINTS } from '../../../api/endpoints.js'
import { API_BASE_URL } from '../../../api/config.js'
import { getAuthToken } from '../../../api/client.js'

const POLL_MS = 2000
const FRAME_INTERVAL_MS = 250 // 4 FPS upper bound (AI rate limit 0.15s)
const FRAME_W = 640
const FRAME_H = 480
const JPEG_QUALITY = 0.7

function classify(err) {
  const s = Number(err?.status ?? err?.statusCode ?? 0)
  if (s === 404) return 'NONE'
  if (s === 401 || s === 403) return 'FORBIDDEN'
  if (s === 0 || s === 502 || s === 503 || s === 504) return 'UNAVAILABLE'
  return 'ERROR'
}

export function useCameraAiRuntime(cameraId) {
  const [entry, setEntry] = useState({ cameraId: null, data: null })
  const [webcam, setWebcam] = useState({ state: 'OFF', error: null, sent: 0, rejected: 0 })
  const [actionError, setActionError] = useState(null)
  const streamRef = useRef(null)
  const timerRef = useRef(null)
  const inFlightRef = useRef(false)
  const canvasRef = useRef(null)
  const videoElRef = useRef(null)
  const cameraRef = useRef(cameraId)
  useEffect(() => {
    cameraRef.current = cameraId
  }, [cameraId])

  const load = useCallback(async (id, signal) => {
    const [status, counts, detection] = await Promise.allSettled([
      camerasApi.getCameraStatus(id, { signal, retries: 0 }),
      camerasApi.getLatestBirdCounts(id, { signal, retries: 0 }),
      camerasApi.getLatestDetections(id, { signal, retries: 0 }),
    ])
    if (signal?.aborted) return
    const sessionState = status.status === 'fulfilled' ? 'ACTIVE' : classify(status.reason)
    setEntry({
      cameraId: id,
      data: {
        sessionState,
        status: status.status === 'fulfilled' ? status.value : null,
        counts: counts.status === 'fulfilled' ? counts.value : null,
        detection: detection.status === 'fulfilled' ? detection.value : null,
        error: status.status === 'rejected' && sessionState !== 'NONE' ? status.reason?.message || 'AI error' : null,
        fetchedAt: new Date().toISOString(),
      },
    })
  }, [])

  useEffect(() => {
    if (!cameraId) return undefined
    const controller = new AbortController()
    const first = setTimeout(() => load(cameraId, controller.signal), 0)
    const t = setInterval(() => load(cameraId, controller.signal), POLL_MS)
    return () => {
      clearTimeout(first)
      controller.abort()
      clearInterval(t)
    }
  }, [cameraId, load])

  const stopWebcamCapture = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = null
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
    if (videoElRef.current) videoElRef.current.srcObject = null
  }, [])

  const sendFrame = useCallback(async () => {
    const video = videoElRef.current
    const id = cameraRef.current
    if (!video || !id || inFlightRef.current || video.readyState < 2) return
    if (!canvasRef.current) {
      canvasRef.current = document.createElement('canvas')
      canvasRef.current.width = FRAME_W
      canvasRef.current.height = FRAME_H
    }
    const canvas = canvasRef.current
    canvas.getContext('2d').drawImage(video, 0, 0, FRAME_W, FRAME_H)
    inFlightRef.current = true
    try {
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', JPEG_QUALITY))
      if (!blob) return
      const resp = await fetch(`${API_BASE_URL || ''}${ENDPOINTS.AI.CAMERA_FRAMES(id)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'image/jpeg', Authorization: `Bearer ${getAuthToken()}` },
        body: blob,
      })
      if (resp.status === 202) {
        setWebcam((w) => ({ ...w, sent: w.sent + 1 }))
      } else if (resp.status === 409) {
        // AI session ended (stopped elsewhere or idle timeout): stop capturing, do not keep sending
        stopWebcamCapture()
        setWebcam((w) => ({ ...w, state: 'OFF', error: 'Phiên AI của webcam đã kết thúc.' }))
      } else if (resp.status !== 429) {
        setWebcam((w) => ({ ...w, rejected: w.rejected + 1, error: `Gửi khung hình thất bại (HTTP ${resp.status})` }))
      }
    } catch {
      setWebcam((w) => ({ ...w, rejected: w.rejected + 1, error: 'Không gửi được khung hình tới AI (mạng).' }))
    } finally {
      inFlightRef.current = false
    }
  }, [stopWebcamCapture])

  const startDemo = useCallback(async () => {
    setActionError(null)
    stopWebcamCapture()
    setWebcam({ state: 'OFF', error: null, sent: 0, rejected: 0 })
    try {
      await camerasApi.startSession(cameraId, 'DEMO_VIDEO')
      load(cameraId)
    } catch (err) {
      setActionError(err?.message || 'Không khởi chạy được video demo.')
    }
  }, [cameraId, load, stopWebcamCapture])

  const startWebcam = useCallback(async (videoElement) => {
    setActionError(null)
    videoElRef.current = videoElement
    if (!navigator.mediaDevices?.getUserMedia) {
      setWebcam({ state: 'BLOCKED', error: 'Trình duyệt không hỗ trợ truy cập camera (cần HTTPS hoặc localhost).', sent: 0, rejected: 0 })
      return
    }
    setWebcam({ state: 'REQUESTING', error: null, sent: 0, rejected: 0 })
    let stream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: FRAME_W }, height: { ideal: FRAME_H }, frameRate: { ideal: 15, max: 30 } },
        audio: false,
      })
    } catch (err) {
      const denied = err?.name === 'NotAllowedError' || err?.name === 'SecurityError'
      const missing = err?.name === 'NotFoundError' || err?.name === 'OverconstrainedError'
      setWebcam({
        state: 'BLOCKED',
        error: denied
          ? 'Chưa được cấp quyền camera cho trang này.'
          : missing
            ? 'Không tìm thấy webcam trên máy.'
            : `Không mở được webcam (${err?.name || 'lỗi'}). Camera có thể đang được ứng dụng khác sử dụng.`,
        sent: 0,
        rejected: 0,
      })
      return
    }
    streamRef.current = stream
    videoElement.srcObject = stream
    try {
      await videoElement.play()
    } catch {
      // autoplay of muted inline video is allowed; ignore
    }
    try {
      await camerasApi.startSession(cameraId, 'LOCAL_CAMERA')
    } catch (err) {
      stopWebcamCapture()
      setWebcam({ state: 'OFF', error: null, sent: 0, rejected: 0 })
      setActionError(err?.message || 'Không khởi chạy được phiên AI cho webcam.')
      return
    }
    setWebcam({ state: 'STREAMING', error: null, sent: 0, rejected: 0 })
    timerRef.current = setInterval(sendFrame, FRAME_INTERVAL_MS)
    load(cameraId)
  }, [cameraId, load, sendFrame, stopWebcamCapture])

  const stopSession = useCallback(async () => {
    setActionError(null)
    stopWebcamCapture()
    setWebcam((w) => ({ ...w, state: 'OFF' }))
    try {
      await camerasApi.stopSession(cameraId)
    } catch (err) {
      if (classify(err) !== 'NONE') setActionError(err?.message || 'Không dừng được phiên AI.')
    }
    load(cameraId)
  }, [cameraId, load, stopWebcamCapture])

  // Leaving the page / switching camera: release the webcam and end its AI session
  useEffect(() => {
    return () => {
      const hadStream = Boolean(streamRef.current)
      stopWebcamCapture()
      if (hadStream && cameraId) camerasApi.stopSession(cameraId).catch(() => {})
    }
  }, [cameraId, stopWebcamCapture])

  const data = entry.cameraId === cameraId ? entry.data : null
  return {
    loading: Boolean(cameraId) && !data,
    sessionState: data?.sessionState || (cameraId ? 'LOADING' : 'NONE'),
    status: data?.status || null,
    counts: data?.counts || null,
    detection: data?.detection || null,
    error: data?.error || null,
    fetchedAt: data?.fetchedAt || null,
    webcam,
    actionError,
    startDemo,
    startWebcam,
    stopSession,
  }
}

export default useCameraAiRuntime
