import assert from 'node:assert/strict'

const results = []

async function runTest(name, fn) {
  try {
    await fn()
    results.push({ name, status: 'PASS' })
  } catch (err) {
    results.push({ name, status: 'FAIL', error: err.message })
    throw err
  }
}

async function importFreshConfig(envVars) {
  const procEnv = globalThis.process.env
  const prev = {
    VITE_API_BASE_URL: procEnv.VITE_API_BASE_URL,
    VITE_API_URL: procEnv.VITE_API_URL,
    VITE_WS_BASE_URL: procEnv.VITE_WS_BASE_URL,
    MODE: procEnv.MODE,
    NODE_ENV: procEnv.NODE_ENV,
  }

  for (const [k, v] of Object.entries(envVars)) {
    if (v === undefined) delete procEnv[k]
    else procEnv[k] = v
  }

  try {
    const mod = await import(`../src/api/config.js?t=${Date.now()}-${Math.random()}`)
    return mod
  } finally {
    for (const [k, v] of Object.entries(prev)) {
      if (v === undefined) delete procEnv[k]
      else procEnv[k] = v
    }
  }
}

await runTest('config: production mode defaults API_BASE_URL to empty string (same-origin)', async () => {
  const cfg = await importFreshConfig({
    VITE_API_BASE_URL: undefined,
    VITE_API_URL: undefined,
    MODE: 'production',
    NODE_ENV: 'production',
  })
  assert.equal(cfg.API_BASE_URL, '')
})

await runTest('config: explicit empty string VITE_API_BASE_URL is preserved even in development', async () => {
  const cfg = await importFreshConfig({
    VITE_API_BASE_URL: '',
    VITE_API_URL: undefined,
    MODE: 'development',
    NODE_ENV: 'development',
  })
  assert.equal(cfg.API_BASE_URL, '')
})

await runTest('config: explicit VITE_API_BASE_URL override is respected', async () => {
  const cfg = await importFreshConfig({
    VITE_API_BASE_URL: 'https://api.swiftletcare.example',
    MODE: 'production',
    NODE_ENV: 'production',
  })
  assert.equal(cfg.API_BASE_URL, 'https://api.swiftletcare.example')
})

await runTest('config: development mode defaults API_BASE_URL to http://localhost:8000', async () => {
  const cfg = await importFreshConfig({
    VITE_API_BASE_URL: undefined,
    VITE_API_URL: undefined,
    MODE: 'development',
    NODE_ENV: 'development',
  })
  assert.equal(cfg.API_BASE_URL, 'http://localhost:8000')
})

const { request, setUnauthorizedHandler, setAuthToken } = await import('../src/api/client.js')

function mockFetch401() {
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ detail: 'Unauthorized' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    })
}

await runTest('client: 401 on /api/auth/login does NOT trigger unauthorized handler', async () => {
  mockFetch401()
  let called = 0
  setUnauthorizedHandler(() => {
    called += 1
  })
  await assert.rejects(
    () => request('/api/auth/login', { method: 'POST', body: { email: 'a@b.c', password: 'x' }, skipAuth: true }),
    (err) => err.status === 401,
  )
  assert.equal(called, 0)
})

await runTest('client: 401 on /api/auth/logout does NOT trigger unauthorized handler', async () => {
  mockFetch401()
  let called = 0
  setUnauthorizedHandler(() => {
    called += 1
  })
  await assert.rejects(
    () => request('/api/auth/logout', { method: 'POST' }),
    (err) => err.status === 401,
  )
  assert.equal(called, 0)
})

await runTest('client: 401 on protected endpoint triggers unauthorized handler once with re-entrancy guard', async () => {
  mockFetch401()
  setAuthToken('expired-jwt-token')
  let called = 0
  setUnauthorizedHandler(() => {
    called += 1
    // Simulate nested protected call or logout during handler
    void request('/api/auth/logout', { method: 'POST' }).catch(() => {})
  })
  await assert.rejects(
    () => request('/api/farms', { method: 'GET' }),
    (err) => err.status === 401,
  )
  assert.equal(called, 1)
  setAuthToken(null)
})

console.log(`API client regression tests: ${results.length}/${results.length} PASSED`)
