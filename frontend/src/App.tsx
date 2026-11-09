import { useEffect, useState } from 'react'
import { Cloud, Rocket, FolderGit2, Plus, UploadCloud, Activity, Database, Settings, GitBranch, ArrowUpRight } from 'lucide-react'

const API = (import.meta as any).env.VITE_API_URL || 'http://localhost:8000/api/v1'
type Project = { id:number; name:string; source_type:string; created_at:string }
export default function App() {
  const [projects,setProjects] = useState<Project[]>([])
  const [name,setName] = useState('')
  const [file,setFile] = useState<File|null>(null)
  const [busy,setBusy] = useState(false)
  const [notice,setNotice] = useState('Loading your projects…')
  const [show,setShow] = useState(false)
  async function refresh() {
    try { const r=await fetch(API+'/projects'); if(!r.ok) throw new Error(); setProjects(await r.json()); setNotice('Control plane connected') }
    catch { setNotice('API not connected yet — check the backend service and VITE_API_URL.') }
  }
  useEffect(()=>{ refresh() },[])
  async function create() {
    if(!name.trim()) return
    setBusy(true)
    try {
      const r=await fetch(API+'/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})})
      if(!r.ok) throw new Error('Could not create project')
      setName(''); setShow(false); await refresh()
    } catch(e:any) { setNotice(e.message || 'Request failed') }
    finally { setBusy(false) }
  }
  async function upload() {
    if(!file || !name.trim()) return
    setBusy(true)
    const body=new FormData(); body.append('project_name',name); body.append('source',file)
    try {
      const r=await fetch(API+'/deployments/upload',{method:'POST',body})
      if(!r.ok) throw new Error(await r.text())
      setName(''); setFile(null); setShow(false); setNotice('ZIP accepted. Deployment is simulated until the secure VPS agent is installed.'); await refresh()
    } catch(e:any) { setNotice(e.message || 'Upload failed') }
    finally { setBusy(false) }
  }
  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><span className="brandIcon"><Cloud size={22}/></span><span>Higlow<span className="accent">Cloud</span></span><small>BETA</small></div>
      <div className="workspace">WORKSPACE</div>
      <nav><button className="selected"><Activity size={17}/> Overview</button><button><FolderGit2 size={17}/> Projects</button><button><Rocket size={17}/> Deployments</button><button><Database size={17}/> Databases</button><button><Settings size={17}/> Settings</button></nav>
      <div className="sideFoot"><div className="avatar">H</div><div><b>HiglowCloud</b><small>Personal workspace</small></div></div>
    </aside>
    <main>
      <header><span>Workspace <i>/</i> Overview</span><span className="user">Personal workspace</span></header>
      <section className="content">
        <div className="intro"><div><small>YOUR CLOUD WORKSPACE</small><h1>Deploy without the complexity.</h1><p>Build, launch and manage your applications from one place.</p></div><button className="primary" onClick={()=>setShow(true)}><Plus size={16}/> New project</button></div>
        <div className="notice"><span className="pulse"></span>{notice}</div>
        <div className="stats"><article><small>Projects</small><b>{projects.length}</b><span>In this workspace</span></article><article><small>Deployments</small><b>—</b><span>Agent connection pending</span></article><article><small>Build minutes</small><b>—</b><span>Metering coming later</span></article><article><small>Databases</small><b>—</b><span>Provisioning coming later</span></article></div>
        <div className="sectionTitle"><div><h2>Projects</h2><p>Your applications and services</p></div><button className="link" onClick={()=>setShow(true)}>Create project <ArrowUpRight size={14}/></button></div>
        {projects.length===0 ? <div className="empty"><div className="emptyIcon"><Rocket size={25}/></div><h3>Start with your first project</h3><p>Import a repository or upload a ZIP archive to get started.</p><div className="actions"><button className="primary" onClick={()=>setShow(true)}><Plus size={15}/> Create project</button><button className="secondary" onClick={()=>setShow(true)}><GitBranch size={15}/> Connect GitHub</button></div></div> :
        <div className="projectGrid">{projects.map(p=><article className="project" key={p.id}><div className="projectIcon"><FolderGit2 size={20}/></div><h3>{p.name}</h3><p>{p.source_type.replace('_',' ')}</p><footer>Created {new Date(p.created_at).toLocaleDateString()} <span>Project #{p.id}</span></footer></article>)}</div>}
        <div className="features"><div><UploadCloud/><b>ZIP uploads</b><small>Upload your source archive.</small></div><div><Github/><b>GitHub integration</b><small>Repository connection is next.</small></div><div><Activity/><b>Deployment activity</b><small>Secure build agent is pending.</small></div></div>
        <p className="disclaimer">HiglowCloud control plane preview. Customer application code is not executed by this API.</p>
      </section>
    </main>
    {show && <div className="backdrop"><div className="modal"><button className="close" onClick={()=>setShow(false)}>×</button><h2>Create a project</h2><p>Give your application a name and optionally upload a ZIP archive.</p><label>Project name<input value={name} onChange={e=>setName(e.target.value)} placeholder="e.g. my-storefront"/></label><label className="file">Source ZIP (optional)<input type="file" accept=".zip,application/zip" onChange={e=>setFile(e.target.files?.[0]||null)}/></label><div className="modalActions"><button className="secondary" onClick={()=>setShow(false)}>Cancel</button><button className="primary" disabled={busy||!name.trim()} onClick={file?upload:create}>{busy?'Working…':file?'Upload and create':'Create project'}</button></div><small className="warning">Deployment execution is simulated until an isolated VPS build agent is connected.</small></div></div>}
  </div>
}
