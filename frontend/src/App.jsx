import React, { useEffect, useMemo, useState } from 'react'
import { approve, dsuHtmlUrl, generate, getDsuList, getPods } from './api.js'

export default function App() {
  const [pods, setPods] = useState([])
  const [podId, setPodId] = useState('')
  const [list, setList] = useState([])
  const [active, setActive] = useState(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    getPods()
      .then((data) => {
        setPods(data)
        if (data.length) setPodId(data[0].id)
      })
      .catch((e) => setMsg(e.message))
  }, [])

  useEffect(() => {
    if (!podId) return
    getDsuList(podId).then((data) => {
      setList(data)
      setActive(data[0]?.date ?? null)
    })
  }, [podId])

  const current = useMemo(() => list.find((d) => d.date === active) ?? null, [list, active])

  async function onGenerate() {
    setBusy(true)
    setMsg('')
    try {
      const r = await generate(podId, { publish: false })
      setMsg(r.pending_approval ? '草稿已生成，等待确认' : `已生成：${r.local_html}`)
      setList(await getDsuList(podId))
      setActive(r.date)
    } catch (e) {
      setMsg(String(e))
    } finally {
      setBusy(false)
    }
  }

  async function onApprove() {
    setBusy(true)
    try {
      const r = await approve(podId, active)
      setMsg(`已发布：${r.url}`)
    } catch (e) {
      setMsg(String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="shell">
      <header>
        <h1>Scrum DSU 看板</h1>
        <div className="sub">每个 pod 一个目录，每天一份静态报告</div>
      </header>

      <div className="bar">
        <select value={podId} onChange={(e) => setPodId(e.target.value)}>
          {pods.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <button onClick={onGenerate} disabled={busy || !podId}>
          生成今日草稿
        </button>
        <button className="primary" onClick={onApprove} disabled={busy || !active}>
          确认并发布
        </button>
        {msg && <span className="msg">{msg}</span>}
      </div>

      <div className="body">
        <aside>
          <div className="aside-title">历史</div>
          {list.length === 0 && <div className="empty">还没有记录</div>}
          {list.map((d) => (
            <button
              key={d.date}
              className={d.date === active ? 'item on' : 'item'}
              onClick={() => setActive(d.date)}
            >
              <span>{d.date}</span>
              <span className={`pill ${d.risk_level ?? 'low'}`}>
                阻塞 {d.open_blockers ?? 0}
              </span>
            </button>
          ))}
        </aside>

        <main>
          {current ? (
            <iframe title={`dsu-${current.date}`} src={dsuHtmlUrl(podId, current.date)} />
          ) : (
            <div className="empty">先跑一次「生成今日草稿」</div>
          )}
        </main>
      </div>
    </div>
  )
}
