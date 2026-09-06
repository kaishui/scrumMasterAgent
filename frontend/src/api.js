const BASE = ''

export async function getPods() {
  const res = await fetch(`${BASE}/api/pods`)
  if (!res.ok) throw new Error('后端未启动，先跑 uvicorn app.main:app')
  return res.json()
}

export async function getDsuList(podId) {
  const res = await fetch(`${BASE}/api/dsu/${podId}`)
  return res.ok ? res.json() : []
}

export async function generate(podId, { date, publish = false } = {}) {
  const params = new URLSearchParams()
  if (date) params.set('date', date)
  params.set('do_publish', String(publish))
  const res = await fetch(`${BASE}/api/dsu/${podId}/generate?${params}`, { method: 'POST' })
  return res.json()
}

export async function approve(podId, date) {
  const res = await fetch(`${BASE}/api/dsu/${podId}/${date}/approve`, { method: 'POST' })
  return res.json()
}

export const dsuHtmlUrl = (podId, date) => `${BASE}/dsu/${podId}/${date}`
