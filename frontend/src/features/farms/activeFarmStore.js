/**
 * INT01-R1: the farm the signed-in user is currently working on, shared by pages and the Header.
 *
 * - Only pages that loaded the farm list from the Gateway (already RBAC-scoped) publish a farm here.
 * - Scoped to the user id, kept in sessionStorage and cleared on logout, so one user's farm is
 *   never shown to the next user of the browser.
 * - The Header never picks a farm on its own (no "first farm" fallback).
 */
import { useSyncExternalStore } from 'react'

const STORAGE_KEY = 'swiftletcare_active_farm'
const listeners = new Set()

function readStorage() {
  try {
    const raw = typeof window !== 'undefined' ? window.sessionStorage.getItem(STORAGE_KEY) : null
    const parsed = raw ? JSON.parse(raw) : null
    return parsed && parsed.userId && parsed.farmId ? parsed : null
  } catch {
    return null
  }
}

let current = readStorage()

function emit() {
  listeners.forEach((l) => l())
}

export function setActiveFarm(userId, farm) {
  if (!userId || !farm?.id) return
  const next = { userId: String(userId), farmId: String(farm.id), farmName: farm.name || '' }
  if (current && current.userId === next.userId && current.farmId === next.farmId && current.farmName === next.farmName) {
    return
  }
  current = next
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  } catch {
    // storage unavailable: in-memory only
  }
  emit()
}

export function clearActiveFarm() {
  current = null
  try {
    window.sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore
  }
  emit()
}

export function getActiveFarm(userId) {
  if (!current || !userId || current.userId !== String(userId)) return null
  return current
}

function subscribe(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Returns { farmId, farmName } for this user, or null when no farm was chosen. */
export function useActiveFarm(userId) {
  const snapshot = useSyncExternalStore(subscribe, () => current, () => null)
  if (!snapshot || !userId || snapshot.userId !== String(userId)) return null
  return snapshot
}
