import { FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft, ArrowUp, Camera, Check, CheckCheck, CircleUserRound, LogOut, MessageSquare, Mic, MicOff, Phone, PhoneCall, PhoneOff, Search, Send, ShieldCheck, UserPlus, Video, VideoOff, X } from 'lucide-react'

const configured = (import.meta as any).env.VITE_API_URL as string | undefined
const apiRoot = (configured || 'https://higlowcloud-api.onrender.com/api/v1').replace(/\\/+$/, '')
const API = apiRoot.endsWith('/api/v1') ? apiRoot : apiRoot.replace(/\\/api$/, '') + '/api/v1'
type Person = { id: number; name: string; email: string; online: boolean; is_contact?: boolean }
type Message = { id: string; sender_id: number; recipient_id: number; body: string; created_at: string; read?: boolean }
type CallEvent = { type: string; from_id?: number; from_name?: string; user_id?: number; message?: Message; data?: any }

export default function NenvaCall() {
  const [token, setToken] = useState(localStorage.getItem('nenva_call_token') || '')
  const [profile, setProfile] = useState<any>(null)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [register, setRegister] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [contacts, setContacts] = useState<Person[]>([])
  const [conversations, setConversations] = useState<any[]>([])
  const [selected, setSelected] = useState<Person | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [draft, setDraft] = useState('')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Person[]>([])
  const [incoming, setIncoming] = useState<any>(null)
  const [offerReady, setOfferReady] = useState(false)
  const [callState, setCallState] = useState<'idle'|'calling'|'ringing'|'connected'>('idle')
  const [mediaMode, setMediaMode] = useState<'audio'|'video'>('audio')
  const [muted, setMuted] = useState(false)
  const [cameraOff, setCameraOff] = useState(false)
  const [showCall, setShowCall] = useState(false)
  const [socketState, setSocketState] = useState('Connecting')
  const [iceServers, setIceServers] = useState<any[]>([{ urls: 'stun:stun.l.google.com:19302' }])
  const wsRef = useRef<WebSocket | null>(null)
  const pcRef = useRef<RTCPeerConnection | null>(null)
  const localStreamRef = useRef<MediaStream | null>(null)
  const remoteStreamRef = useRef<MediaStream | null>(null)
  const pendingOfferRef = useRef<any>(null)
  const pendingIceRef = useRef<any[]>([])
  const localVideoRef = useRef<HTMLVideoElement>(null)
  const remoteVideoRef = useRef<HTMLVideoElement>(null)
  const selectedRef = useRef<Person | null>(null)

  useEffect(() => { selectedRef.current = selected }, [selected])

  const request = useCallback(async (path: string, init: RequestInit = {}, authToken = token) => {
    const headers: any = { ...(init.headers || {}) }
    if (authToken) headers.Authorization = 'Bearer ' + authToken
    if (!(init.body instanceof FormData)) headers['Content-Type'] = 'application/json'
    let response: Response
    try { response = await fetch(API + path, { ...init, headers }) }
    catch { throw new Error('Cannot connect to Nenva Call. Check your internet connection.') }
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'The request could not be completed.')
    return data
  }, [token])

  const refreshLists = useCallback(async () => {
    const [c, v] = await Promise.all([request('/nenva-call/contacts'), request('/nenva-call/conversations')])
    setContacts(c); setConversations(v)
  }, [request])

  const loadMessages = useCallback(async (person: Person) => {
    setSelected(person)
    setMessages(await request('/nenva-call/messages/' + person.id))
  }, [request])

  const clearCall = useCallback((send = false) => {
    const peer = selectedRef.current
    if (send && peer) wsRef.current?.send(JSON.stringify({ type: 'hangup', to: peer.id, data: {} }))
    pcRef.current?.close(); pcRef.current = null
    localStreamRef.current?.getTracks().forEach(t => t.stop()); localStreamRef.current = null
    remoteStreamRef.current?.getTracks().forEach(t => t.stop()); remoteStreamRef.current = null
    pendingOfferRef.current = null; pendingIceRef.current = []
    setOfferReady(false)
    setIncoming(null); setCallState('idle'); setShowCall(false); setMuted(false); setCameraOff(false)
  }, [])

  useEffect(() => {
    if (!token) return
    let active = true
    request('/nenva-call/config').then(async data => {
      if (!active) return
      setProfile(data.user); setIceServers(data.ice_servers)
      await refreshLists()
    }).catch(e => { if (active) { setError(e.message); setToken(''); localStorage.removeItem('nenva_call_token') } })
    let socket: WebSocket | null = null
    let heartbeat: number | undefined
    let retryTimer: number | undefined
    let attempts = 0
    const openSocket = async () => {
      const { ticket } = await request('/nenva-call/socket-ticket', { method: 'POST', body: '{}' })
      if (!active) return
      const wsUrl = API.replace(/^http/, 'ws') + '/nenva-call/ws?ticket=' + encodeURIComponent(ticket)
      const ws = new WebSocket(wsUrl)
      socket = ws
      wsRef.current = ws
      ws.onopen = () => {
        attempts = 0
        setSocketState('Connected')
        if (heartbeat) window.clearInterval(heartbeat)
        heartbeat = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }))
        }, 25000)
      }
      ws.onclose = () => {
        setSocketState('Reconnecting')
        if (heartbeat) window.clearInterval(heartbeat)
        if (active) {
          const delay = Math.min(1000 * (2 ** attempts), 30000)
          attempts += 1
          retryTimer = window.setTimeout(() => openSocket().catch(e => { if (active) setError(e.message) }), delay)
        }
      }
      ws.onerror = () => setSocketState('Offline')
      ws.onmessage = async event => {
        let data: CallEvent
        try { data = JSON.parse(event.data) } catch { return }
        if (data.type === 'presence') setContacts(old => old.map(p => p.id === data.user_id ? { ...p, online: !!data.online } : p))
        if (data.type === 'message') {
          const m = data.message as Message
          if (selectedRef.current && (m.sender_id === selectedRef.current.id || m.recipient_id === selectedRef.current.id)) {
            setMessages(old => old.some(x => x.id === m.id) ? old : [...old, m])
          }
          refreshLists().catch(() => {})
        }
        if (data.type === 'call') {
          setIncoming({ id: data.from_id, name: data.from_name, media: data.data?.media || 'audio' })
          setMediaMode(data.data?.media === 'video' ? 'video' : 'audio')
          setCallState('ringing')
        }
        if (data.type === 'offer') {
          pendingOfferRef.current = { from: data.from_id, offer: data.data?.description }
          setOfferReady(!!data.data?.description)
        }
        if (data.type === 'answer' && pcRef.current && data.data?.description) {
          await pcRef.current.setRemoteDescription(data.data.description)
          setCallState('connected')
          for (const candidate of pendingIceRef.current.splice(0)) await pcRef.current.addIceCandidate(candidate).catch(() => {})
        }
        if (data.type === 'ice' && data.data?.candidate) {
          if (pcRef.current?.remoteDescription) await pcRef.current.addIceCandidate(data.data.candidate).catch(() => {})
          else pendingIceRef.current.push(data.data.candidate)
        }
        if (data.type === 'hangup' || data.type === 'decline') clearCall(false)
        if (data.type === 'error') setError(data.data?.message || 'Call connection error.')
      }
    }
    openSocket().catch(e => { if (active) { setSocketState('Offline'); setError(e.message) } })
    return () => {
      active = false
      if (heartbeat) window.clearInterval(heartbeat)
      if (retryTimer) window.clearTimeout(retryTimer)
      socket?.close()
      wsRef.current = null
      clearCall(false)
    }
  }, [token])

  const authenticate = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError('')
    try {
      const path = register ? '/auth/register' : '/auth/login'
      const payload = register ? { name, email, password } : { email, password }
      const data = await request(path, { method: 'POST', body: JSON.stringify(payload) }, '')
      localStorage.setItem('nenva_call_token', data.access_token)
      setToken(data.access_token)
    } catch (e: any) { setError(e.message) }
    finally { setBusy(false) }
  }

  const searchUsers = async (e: FormEvent) => {
    e.preventDefault(); setError('')
    try { setResults(await request('/nenva-call/contacts/search?q=' + encodeURIComponent(query))) }
    catch (e: any) { setError(e.message) }
  }

  const addContact = async (person: Person) => {
    setBusy(true); setError('')
    try { await request('/nenva-call/contacts', { method: 'POST', body: JSON.stringify({ user_id: person.id }) }); await refreshLists(); setResults([]); setQuery(''); setNotice(person.name + ' added to contacts.') }
    catch (e: any) { setError(e.message) }
    finally { setBusy(false) }
  }

  const sendMessage = async (e: FormEvent) => {
    e.preventDefault()
    if (!selected || !draft.trim()) return
    const body = draft.trim(); setDraft('')
    try {
      const message = await request('/nenva-call/messages', { method: 'POST', body: JSON.stringify({ recipient_id: selected.id, body }) })
      setMessages(old => [...old, message]); refreshLists().catch(() => {})
    } catch (e: any) { setError(e.message); setDraft(body) }
  }

  const makePeer = async (person: Person, mode: 'audio'|'video') => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: mode === 'video' })
    localStreamRef.current = stream
    if (localVideoRef.current) localVideoRef.current.srcObject = stream
    const pc = new RTCPeerConnection({ iceServers })
    pcRef.current = pc
    const remote = new MediaStream(); remoteStreamRef.current = remote
    if (remoteVideoRef.current) remoteVideoRef.current.srcObject = remote
    stream.getTracks().forEach(track => pc.addTrack(track, stream))
    pc.ontrack = event => { event.streams[0]?.getTracks().forEach(track => remote.addTrack(track)); if (remoteVideoRef.current) remoteVideoRef.current.srcObject = remote }
    pc.onicecandidate = event => { if (event.candidate) wsRef.current?.send(JSON.stringify({ type: 'ice', to: person.id, data: { candidate: event.candidate } })) }
    pc.onconnectionstatechange = () => {
      if (pc.connectionState === 'connected') setCallState('connected')
      if (['failed','disconnected','closed'].includes(pc.connectionState) && callState !== 'idle') setNotice('Call connection interrupted.')
    }
    return pc
  }

  const startCall = async (mode: 'audio'|'video') => {
    if (!selected || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) { setError('Call service is not connected. Please wait a moment.'); return }
    setError(''); setMediaMode(mode); setCallState('calling'); setShowCall(true)
    try {
      const pc = await makePeer(selected, mode)
      wsRef.current.send(JSON.stringify({ type: 'call', to: selected.id, data: { media: mode } }))
      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)
      wsRef.current.send(JSON.stringify({ type: 'offer', to: selected.id, data: { description: offer } }))
    } catch (e: any) { clearCall(false); setError(e.name === 'NotAllowedError' ? 'Allow microphone/camera access in your browser settings, then try again.' : e.message || 'Could not start the call.') }
  }

  const acceptCall = async () => {
    if (!incoming || !pendingOfferRef.current?.offer) { setError('The caller connection is not ready. Ask them to call again.'); return }
    const caller = contacts.find(p => p.id === incoming.id) || { id: incoming.id, name: incoming.name, email: '', online: true }
    setSelected(caller); selectedRef.current = caller; setShowCall(true); setCallState('calling')
    try {
      const pc = await makePeer(caller, incoming.media)
      await pc.setRemoteDescription(pendingOfferRef.current.offer)
      for (const candidate of pendingIceRef.current.splice(0)) await pc.addIceCandidate(candidate).catch(() => {})
      const answer = await pc.createAnswer()
      await pc.setLocalDescription(answer)
      wsRef.current?.send(JSON.stringify({ type: 'answer', to: caller.id, data: { description: answer } }))
      setIncoming(null); setCallState('connected')
    } catch (e: any) { clearCall(true); setError(e.message || 'Could not answer the call.') }
  }

  const logout = () => { clearCall(false); wsRef.current?.close(); localStorage.removeItem('nenva_call_token'); setToken(''); setProfile(null); setContacts([]); setConversations([]); setSelected(null); setMessages([]) }

  if (!token || !profile) return <div className="nc-auth"><div className="nc-auth-card"><div className="nc-logo">N</div><span className="nc-kicker">HIGLOWCLOUD COMMUNICATIONS</span><h1>Nenva Call</h1><p>Private messages and voice and video calls in one place.</p><form onSubmit={authenticate}>{register && <label>Your name<input required value={name} onChange={e=>setName(e.target.value)} placeholder="Full name"/></label>}<label>Email address<input type="email" required value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@example.com"/></label><label>Password<input type="password" required minLength={register?10:1} value={password} onChange={e=>setPassword(e.target.value)} placeholder="Password"/></label><button className="nc-primary" disabled={busy}>{busy?'Please wait…':register?'Create account':'Sign in'}</button></form><button className="nc-link" onClick={()=>{setRegister(!register);setError('')}}>{register?'Already have an account? Sign in':'New to HiglowCloud? Create an account'}</button>{error&&<div className="nc-error">{error}</div>}<small>Accounts are shared with HiglowCloud. Email and phone verification are not enabled in this first connected version.</small></div></div>

  return <div className="nc-app">
    <aside className="nc-sidebar">
      <div className="nc-brand"><div className="nc-brand-mark">N</div><div><b>Nenva Call</b><small>Secure communication</small></div></div>
      <div className="nc-profile"><div className="nc-avatar">{(profile.name||profile.email).slice(0,1).toUpperCase()}</div><div><b>{profile.name||'Your account'}</b><small>{socketState}</small></div><button title="Sign out" onClick={logout}><LogOut size={17}/></button></div>
      <form className="nc-search" onSubmit={searchUsers}><Search size={16}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Find people by name or email"/><button aria-label="Search"><ArrowUp size={15}/></button></form>
      {results.length>0&&<div className="nc-search-results">{results.map(p=><div key={p.id}><span><b>{p.name}</b><small>{p.email}</small></span>{p.is_contact?<button onClick={()=>loadMessages(p)}>Open</button>:<button disabled={busy} onClick={()=>addContact(p)}><UserPlus size={15}/></button>}</div>)}</div>}
      <div className="nc-section-label">MESSAGES</div>
      <div className="nc-contact-list">{contacts.map(p=><button key={p.id} className={'nc-contact '+(selected?.id===p.id?'active':'')} onClick={()=>loadMessages(p)}><span className="nc-avatar small">{p.name.slice(0,1).toUpperCase()}</span><span className="nc-contact-text"><b>{p.name}</b><small>{p.online?'Online':p.email}</small></span><i className={p.online?'online':''}/></button>)}</div>
      <div className="nc-sidebar-bottom"><ShieldCheck size={15}/> Messages are stored securely in your HiglowCloud database.</div>
    </aside>
    <main className="nc-main">
      <header className="nc-top"><div><span className="nc-kicker">YOUR COMMUNICATIONS</span><h2>{selected?.name||'Welcome to Nenva Call'}</h2><small>{selected?selected.email:'Choose a contact or find someone to start a conversation.'}</small></div>{selected&&<div className="nc-actions"><button title="Voice call" onClick={()=>startCall('audio')}><Phone size={18}/></button><button title="Video call" onClick={()=>startCall('video')}><Video size={18}/></button></div>}</header>
      {error&&<div className="nc-banner error">{error}<button onClick={()=>setError('')}><X size={15}/></button></div>}
      {notice&&<div className="nc-banner">{notice}<button onClick={()=>setNotice('')}><X size={15}/></button></div>}
      {showCall&&<section className="nc-call-stage"><div className="nc-video-grid"><video ref={remoteVideoRef} autoPlay playsInline/><video className="nc-local-video" ref={localVideoRef} autoPlay playsInline muted/><div className="nc-call-label">{callState==='connected'?'Call connected':callState==='calling'?'Connecting call…':'In call with '+(selected?.name||'contact')}</div></div><div className="nc-call-controls"><button className={muted?'selected':''} onClick={()=>{const t=localStreamRef.current?.getAudioTracks()[0];if(t)t.enabled=!t.enabled;setMuted(!muted)}}>{muted?<MicOff/>:<Mic/>}</button>{mediaMode==='video'&&<button className={cameraOff?'selected':''} onClick={()=>{const t=localStreamRef.current?.getVideoTracks()[0];if(t)t.enabled=!t.enabled;setCameraOff(!cameraOff)}}>{cameraOff?<VideoOff/>:<Camera/>}</button>}<button className="hangup" onClick={()=>clearCall(true)}><PhoneOff/></button></div></section>}
      {!selected&&!showCall&&<div className="nc-empty"><div className="nc-empty-icon"><MessageSquare size={32}/></div><h3>Your conversations start here</h3><p>Search for a HiglowCloud user by name or email, add them, then send a message or start a call.</p></div>}
      {selected&&!showCall&&<><div className="nc-messages">{messages.map(m=><div key={m.id} className={'nc-message '+(m.sender_id===profile.id?'mine':'')}><div>{m.body}</div><small>{new Date(m.created_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})} {m.sender_id===profile.id&&(m.read?<CheckCheck size={13}/>:<Check size={13}/>)}</small></div>)}</div><form className="nc-compose" onSubmit={sendMessage}><input value={draft} onChange={e=>setDraft(e.target.value)} placeholder={'Message '+selected.name+'…'} maxLength={5000}/><button disabled={!draft.trim()} aria-label="Send message"><Send size={18}/></button></form></>}
      {incoming&&<div className="nc-incoming"><div className="nc-incoming-card"><div className="nc-avatar large">{incoming.name.slice(0,1).toUpperCase()}</div><span className="nc-kicker">INCOMING {incoming.media==='video'?'VIDEO':'VOICE'} CALL</span><h3>{incoming.name}</h3><p>is calling you</p><div><button className="decline" onClick={()=>{wsRef.current?.send(JSON.stringify({type:'decline',to:incoming.id,data:{}}));clearCall(false)}}><PhoneOff/> Decline</button><button className="accept" disabled={!offerReady} onClick={acceptCall}><PhoneCall/> {offerReady?'Answer':'Connecting…'}</button></div></div></div>}
    </main>
  </div>
}
