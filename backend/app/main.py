from __future__ import annotations
import base64,hashlib,hmac,json,os,re,secrets,uuid,zipfile,io,time,urllib.request,urllib.error,urllib.parse
from datetime import datetime,timedelta,timezone
from pathlib import Path,PurePosixPath
from typing import Optional
from fastapi import FastAPI,Depends,HTTPException,UploadFile,File,Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from pydantic import BaseModel,Field
from sqlalchemy import String,DateTime,ForeignKey,Text,Boolean,Float,select,desc,func,inspect,text
from sqlalchemy.orm import Mapped,mapped_column,Session
from .database import Base,engine,get_db
from cryptography.fernet import Fernet,InvalidToken
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding

UTC=timezone.utc
def now(): return datetime.now(UTC)
def slug(s): return re.sub(r"[^a-z0-9]+","-",s.lower()).strip("-")[:100] or "project"

class User(Base):
 __tablename__="users"
 id:Mapped[int]=mapped_column(primary_key=True)
 email:Mapped[str]=mapped_column(String(255),unique=True,index=True)
 name:Mapped[str]=mapped_column(String(120),default="")
 password_hash:Mapped[str]=mapped_column(String(255))
 active:Mapped[bool]=mapped_column(Boolean,default=True)
 admin:Mapped[bool]=mapped_column(Boolean,default=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Organization(Base):
 __tablename__="organizations"
 id:Mapped[int]=mapped_column(primary_key=True)
 name:Mapped[str]=mapped_column(String(120))
 slug:Mapped[str]=mapped_column(String(130),unique=True)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Membership(Base):
 __tablename__="memberships"
 id:Mapped[int]=mapped_column(primary_key=True)
 user_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
 org_id:Mapped[int]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True)
 role:Mapped[str]=mapped_column(String(30),default="owner")
class Project(Base):
 __tablename__="projects"
 id:Mapped[int]=mapped_column(primary_key=True)
 org_id:Mapped[int]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True)
 name:Mapped[str]=mapped_column(String(120))
 slug:Mapped[str]=mapped_column(String(120))
 framework:Mapped[str]=mapped_column(String(60),default="auto")
 source_type:Mapped[str]=mapped_column(String(30),default="manual")
 source_url:Mapped[str]=mapped_column(String(1000),nullable=True)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
 updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)
class Deployment(Base):
 __tablename__="deployments"
 id:Mapped[int]=mapped_column(primary_key=True)
 uid:Mapped[str]=mapped_column(String(36),default=lambda:str(uuid.uuid4()),unique=True,index=True)
 org_id:Mapped[int]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True)
 project_id:Mapped[int]=mapped_column(ForeignKey("projects.id",ondelete="CASCADE"),index=True)
 status:Mapped[str]=mapped_column(String(30),default="queued")
 source_type:Mapped[str]=mapped_column(String(30),default="github")
 source_ref:Mapped[str]=mapped_column(String(1000),default="")
 logs:Mapped[str]=mapped_column(Text,default="Queued; waiting for isolated build worker.")
 deploy_url:Mapped[str]=mapped_column(String(1000),default="")
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
 finished_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=True)
class EnvVar(Base):
 __tablename__="environment_variables"
 id:Mapped[int]=mapped_column(primary_key=True)
 org_id:Mapped[int]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True)
 project_id:Mapped[int]=mapped_column(ForeignKey("projects.id",ondelete="CASCADE"),index=True)
 key:Mapped[str]=mapped_column(String(180))
 value_enc:Mapped[str]=mapped_column(Text)
 secret:Mapped[bool]=mapped_column(Boolean,default=True)
 updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)
class Domain(Base):
 __tablename__="domains"
 id:Mapped[int]=mapped_column(primary_key=True)
 org_id:Mapped[int]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True)
 project_id:Mapped[int]=mapped_column(ForeignKey("projects.id",ondelete="CASCADE"),index=True)
 hostname:Mapped[str]=mapped_column(String(253),unique=True,index=True)
 token:Mapped[str]=mapped_column(String(100),default=lambda:secrets.token_urlsafe(24))
 status:Mapped[str]=mapped_column(String(30),default="pending_dns")
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class DatabaseResource(Base):
 __tablename__="database_resources"
 id:Mapped[int]=mapped_column(primary_key=True)
 org_id:Mapped[int]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True)
 project_id:Mapped[int]=mapped_column(ForeignKey("projects.id",ondelete="CASCADE"),index=True)
 name:Mapped[str]=mapped_column(String(120))
 engine:Mapped[str]=mapped_column(String(20),default="postgres")
 status:Mapped[str]=mapped_column(String(30),default="requested")
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Usage(Base):
 __tablename__="usage_events"
 id:Mapped[int]=mapped_column(primary_key=True)
 org_id:Mapped[int]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True)
 project_id:Mapped[int]=mapped_column(ForeignKey("projects.id",ondelete="SET NULL"),nullable=True)
 metric:Mapped[str]=mapped_column(String(60))
 quantity:Mapped[float]=mapped_column(Float,default=0)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Audit(Base):
 __tablename__="audit_logs"
 id:Mapped[int]=mapped_column(primary_key=True)
 org_id:Mapped[int]=mapped_column(ForeignKey("organizations.id",ondelete="SET NULL"),nullable=True,index=True)
 user_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),nullable=True)
 action:Mapped[str]=mapped_column(String(100))
 target:Mapped[str]=mapped_column(String(180),default="")
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class GitHubInstallation(Base):
 __tablename__="github_installations"
 id:Mapped[int]=mapped_column(primary_key=True)
 org_id:Mapped[int]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),unique=True,index=True)
 installation_id:Mapped[int]=mapped_column(unique=True,index=True)
 account_login:Mapped[str]=mapped_column(String(255))
 account_type:Mapped[str]=mapped_column(String(40),default="User")
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class GitHubConnectState(Base):
 __tablename__="github_connect_states"
 state_hash:Mapped[str]=mapped_column(String(64),primary_key=True)
 user_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"))
 org_id:Mapped[int]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"))
 expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class GitHubDelivery(Base):
 __tablename__="github_deliveries"
 delivery_id:Mapped[str]=mapped_column(String(100),primary_key=True)
 received_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

Base.metadata.create_all(bind=engine)

# Upgrade the original unauthenticated MVP tables in place without dropping customer data.
def migrate_legacy_schema():
 additions={
  "projects":{
   "org_id":"INTEGER REFERENCES organizations(id)","slug":"VARCHAR(120)","framework":"VARCHAR(60)",
   "source_url":"VARCHAR(1000)","source_ref":"VARCHAR(255)","updated_at":"TIMESTAMP"
  },
  "deployments":{
   "uid":"VARCHAR(36)","org_id":"INTEGER REFERENCES organizations(id)","source_type":"VARCHAR(30)",
   "source_ref":"VARCHAR(1000)","deploy_url":"VARCHAR(1000)","finished_at":"TIMESTAMP"
  }
 }
 with engine.begin() as conn:
  tables=set(inspect(conn).get_table_names())
  for table,columns in additions.items():
   if table not in tables: continue
   existing={x["name"] for x in inspect(conn).get_columns(table)}
   for name,definition in columns.items():
    if name not in existing: conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
  if "projects" in tables:
   conn.execute(text("UPDATE projects SET slug = 'legacy-' || id WHERE slug IS NULL OR slug = ''"))
   conn.execute(text("UPDATE projects SET framework = 'auto' WHERE framework IS NULL OR framework = ''"))
   conn.execute(text("UPDATE projects SET updated_at = created_at WHERE updated_at IS NULL"))
  if "deployments" in tables:
   conn.execute(text("UPDATE deployments SET source_type = 'legacy' WHERE source_type IS NULL OR source_type = ''"))
   conn.execute(text("UPDATE deployments SET source_ref = '' WHERE source_ref IS NULL"))
   conn.execute(text("UPDATE deployments SET deploy_url = '' WHERE deploy_url IS NULL"))
   for row in conn.execute(text("SELECT id FROM deployments WHERE uid IS NULL")).fetchall():
    conn.execute(text("UPDATE deployments SET uid = :uid WHERE id = :id"),{"uid":str(uuid.uuid4()),"id":row[0]})
migrate_legacy_schema()

app=FastAPI(title="HiglowCloud API",version="1.0.0")
# Keep the deployed dashboard origins trusted even if Render has an outdated hostname.
origins={"https://higlowcloud.onrender.com","https://higlowcloud-web.onrender.com","http://localhost:5173"}
origins.update(x.strip() for x in os.getenv("FRONTEND_ORIGIN","").split(",") if x.strip())
app.add_middleware(CORSMiddleware,allow_origins=sorted(origins),allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
secret=os.getenv("SECRET_KEY","")
if os.getenv("APP_ENV")=="production" and len(secret)<32: raise RuntimeError("Set SECRET_KEY to 32+ random characters.")
if not secret: secret=secrets.token_urlsafe(48)
SECRET=secret.encode()
FERNET=Fernet(base64.urlsafe_b64encode(hashlib.sha256(SECRET+b"env").digest()))
ADMINS={x.strip().lower() for x in os.getenv("ADMIN_EMAILS","").split(",") if x.strip()}
auth=HTTPBearer(auto_error=False)
def pw_hash(p):
 salt=secrets.token_bytes(16); d=hashlib.scrypt(p.encode(),salt=salt,n=16384,r=8,p=1,dklen=32)
 return base64.urlsafe_b64encode(salt+d).decode()
def pw_check(p,stored):
 try:
  raw=base64.urlsafe_b64decode(stored); return hmac.compare_digest(hashlib.scrypt(p.encode(),salt=raw[:16],n=16384,r=8,p=1,dklen=32),raw[16:])
 except Exception:return False
def enc(v):return FERNET.encrypt(v.encode()).decode()
def dec(v):
 try:return FERNET.decrypt(v.encode()).decode()
 except InvalidToken:raise HTTPException(500,"Environment encryption key mismatch; restore SECRET_KEY.")
def b64(b):return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def make_token(user,org):
 a=b64(b'{"alg":"HS256","typ":"JWT"}'); b=b64(json.dumps({"sub":user.id,"org":org,"exp":int((now()+timedelta(hours=24)).timestamp())}).encode()); body=a+"."+b
 return body+"."+b64(hmac.new(SECRET,body.encode(),hashlib.sha256).digest())
def token_data(t):
 try:
  a,b,c=t.split("."); body=a+"."+b; sig=base64.urlsafe_b64decode(c+"="*((4-len(c)%4)%4))
  if not hmac.compare_digest(hmac.new(SECRET,body.encode(),hashlib.sha256).digest(),sig):raise ValueError()
  d=json.loads(base64.urlsafe_b64decode(b+"="*((4-len(b)%4)%4)))
  if d["exp"]<int(now().timestamp()):raise ValueError()
  return d
 except Exception:raise HTTPException(401,"Session expired. Please sign in again.")
def current(credentials:HTTPAuthorizationCredentials=Depends(auth),db:Session=Depends(get_db)):
 if not credentials:raise HTTPException(401,"Sign in to continue.")
 d=token_data(credentials.credentials); u=db.get(User,int(d["sub"]))
 if not u or not u.active:raise HTTPException(401,"Account unavailable.")
 m=db.scalar(select(Membership).where(Membership.user_id==u.id,Membership.org_id==int(d["org"])))
 if not m:raise HTTPException(403,"Workspace access denied.")
 return {"user":u,"org":m.org_id,"role":m.role}
def platform_admin(ctx=Depends(current)):
 if not ctx["user"].admin:raise HTTPException(403,"Platform administrator access required.")
 return ctx
def project(db,ctx,pid):
 p=db.scalar(select(Project).where(Project.id==pid,Project.org_id==ctx["org"]))
 if not p:raise HTTPException(404,"Project not found.")
 return p
def log(db,ctx,action,target=""):db.add(Audit(org_id=ctx["org"],user_id=ctx["user"].id,action=action,target=str(target)[:180]))
def dep_dict(d):return {"id":d.id,"uid":d.uid,"project_id":d.project_id,"status":d.status,"source_type":d.source_type,"source_ref":d.source_ref,"logs":d.logs,"deploy_url":d.deploy_url,"created_at":d.created_at,"finished_at":d.finished_at}

class Register(BaseModel):
 email:str;password:str=Field(min_length=10,max_length=128);name:str=Field(min_length=1,max_length=120)
class Login(BaseModel):email:str;password:str
class ProjectIn(BaseModel):
 name:str=Field(min_length=1,max_length=120);framework:str="auto";source_type:str="manual";source_url:Optional[str]=None
class EnvIn(BaseModel):key:str=Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,179}$");value:str=Field(max_length=10000);secret:bool=True
class DomainIn(BaseModel):hostname:str
class DbIn(BaseModel):name:str=Field(min_length=1,max_length=120);engine:str="postgres"

@app.get("/")
def root():
 return {"service":"HiglowCloud API","status":"ok","health":"/health","api":"/api/v1"}

@app.get("/health")
def health(db:Session=Depends(get_db)):
 try:db.execute(select(1))
 except Exception:raise HTTPException(503,"Database unavailable.")
 return {"status":"ok","database":"connected","service":"higlowcloud-api","version":"1.0.0"}
@app.get("/api/v1/status")
def status():return {"control_plane":"operational","build_workers":"not_connected","runtime_nodes":"not_connected","domain_edge":"not_connected","database_provisioner":"not_connected"}
@app.post("/api/v1/auth/register",status_code=201)
def register(x:Register,db:Session=Depends(get_db)):
 email=x.email.strip().lower()
 if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",email):raise HTTPException(422,"Enter a valid email address.")
 if db.scalar(select(User).where(User.email==email)):raise HTTPException(409,"Email already registered.")
 u=User(email=email,name=x.name.strip(),password_hash=pw_hash(x.password),admin=email in ADMINS)
 org=Organization(name=(x.name.strip()+" workspace")[:120],slug=slug(email.split("@")[0])+"-"+secrets.token_hex(3))
 db.add_all([u,org]);db.flush();db.add(Membership(user_id=u.id,org_id=org.id,role="owner"))
 # Only the configured platform owner may adopt legacy pre-authentication records.
 if u.admin:
  legacy=db.scalars(select(Project).where(Project.org_id.is_(None))).all()
  for old_project in legacy:
   old_project.org_id=org.id
   if not old_project.slug: old_project.slug=slug(old_project.name)+"-legacy-"+str(old_project.id)
   if not old_project.framework: old_project.framework="auto"
   if not old_project.updated_at: old_project.updated_at=old_project.created_at or now()
  for old_deploy in db.scalars(select(Deployment).where(Deployment.org_id.is_(None))).all():
   parent=db.get(Project,old_deploy.project_id)
   if parent and parent.org_id==org.id: old_deploy.org_id=org.id
 db.add(Audit(org_id=org.id,user_id=u.id,action="auth.register",target=email));db.commit()
 return {"access_token":make_token(u,org.id),"token_type":"bearer","user":{"id":u.id,"email":u.email,"name":u.name},"workspace":{"id":org.id,"name":org.name}}
@app.post("/api/v1/auth/login")
def login(x:Login,db:Session=Depends(get_db)):
 u=db.scalar(select(User).where(User.email==x.email.strip().lower()))
 if not u or not pw_check(x.password,u.password_hash):raise HTTPException(401,"Email or password is incorrect.")
 if not u.active:raise HTTPException(403,"Account disabled.")
 m=db.scalar(select(Membership).where(Membership.user_id==u.id).order_by(Membership.id))
 if not m:raise HTTPException(403,"No workspace assigned.")
 return {"access_token":make_token(u,m.org_id),"token_type":"bearer","user":{"id":u.id,"email":u.email,"name":u.name},"workspace":{"id":m.org_id}}
@app.get("/api/v1/auth/me")
def me(ctx=Depends(current)):
 u=ctx["user"];return {"id":u.id,"email":u.email,"name":u.name,"is_platform_admin":u.admin,"role":ctx["role"],"organization_id":ctx["org"]}

# GitHub App integration. Installation credentials are exchanged on demand and never stored.
def github_app_config():
 app_id=os.getenv("GITHUB_APP_ID","").strip()
 private_key=os.getenv("GITHUB_APP_PRIVATE_KEY","").replace("\\n","\\n").strip()
 app_slug=os.getenv("GITHUB_APP_SLUG","higlowcloud").strip()
 if not app_id or not private_key:raise HTTPException(503,"GitHub App is not configured on the API service.")
 return app_id,private_key,app_slug
def github_app_jwt():
 app_id,key,_=github_app_config()
 try:
  private=serialization.load_pem_private_key(key.encode(),password=None)
  header=b64(json.dumps({"alg":"RS256","typ":"JWT"}).encode())
  payload=b64(json.dumps({"iat":int(time.time())-60,"exp":int(time.time())+540,"iss":app_id}).encode())
  body=header+"."+payload
  signature=private.sign(body.encode(),padding.PKCS1v15(),hashes.SHA256())
  return body+"."+b64(signature)
 except Exception:raise HTTPException(503,"GitHub App private key is invalid. Check GITHUB_APP_PRIVATE_KEY.")
def github_api(path,token=None,method="GET",body=None):
 headers={"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"HiglowCloud"}
 headers["Authorization"]="Bearer "+(token or github_app_jwt())
 data=json.dumps(body or {}).encode() if body is not None else None
 if data is not None:headers["Content-Type"]="application/json"
 req=urllib.request.Request("https://api.github.com"+path,data=data,headers=headers,method=method)
 try:
  with urllib.request.urlopen(req,timeout=20) as response:return json.loads(response.read().decode() or "{}")
 except urllib.error.HTTPError as exc:
  detail=exc.read().decode(errors="replace")[:500]
  raise HTTPException(502,"GitHub API request failed ("+str(exc.code)+"): "+detail)
 except Exception:raise HTTPException(502,"Could not reach GitHub. Try again.")
def github_installation_token(installation_id):
 result=github_api("/app/installations/"+str(installation_id)+"/access_tokens",method="POST",body={})
 token=result.get("token")
 if not token:raise HTTPException(502,"GitHub did not issue an installation access token.")
 return token
def github_frontend_url():
 return os.getenv("FRONTEND_ORIGIN","https://higlowcloud.onrender.com").split(",")[0].strip().rstrip("/")
@app.post("/api/v1/integrations/github/connect")
def github_connect(ctx=Depends(current),db:Session=Depends(get_db)):
 _,_,app_slug=github_app_config()
 state=secrets.token_urlsafe(32)
 db.add(GitHubConnectState(state_hash=hashlib.sha256(state.encode()).hexdigest(),user_id=ctx["user"].id,org_id=ctx["org"],expires_at=now()+timedelta(minutes=10)))
 db.commit()
 return {"url":"https://github.com/apps/"+urllib.parse.quote(app_slug,safe="")+"/installations/new?state="+urllib.parse.quote(state,safe=""),"expires_in":600}
@app.get("/api/v1/integrations/github/callback")
def github_callback(installation_id:int, state:str, setup_action:str="install", db:Session=Depends(get_db)):
 if setup_action not in {"install","update"}:raise HTTPException(400,"GitHub App installation was not completed.")
 state_hash=hashlib.sha256(state.encode()).hexdigest()
 saved=db.get(GitHubConnectState,state_hash)
 if not saved or saved.expires_at.replace(tzinfo=UTC) < now():raise HTTPException(400,"GitHub connection link expired. Return to HiglowCloud and connect again.")
 installation=github_api("/app/installations/"+str(installation_id))
 account=installation.get("account") or {}
 login=account.get("login")
 if not login:raise HTTPException(502,"GitHub did not return the installation account.")
 existing=db.scalar(select(GitHubInstallation).where(GitHubInstallation.org_id==saved.org_id))
 if existing:
  existing.installation_id=installation_id;existing.account_login=login;existing.account_type=account.get("type","User")
 else:db.add(GitHubInstallation(org_id=saved.org_id,installation_id=installation_id,account_login=login,account_type=account.get("type","User")))
 db.delete(saved);db.commit()
 return RedirectResponse(github_frontend_url()+"/?github=connected",status_code=303)
@app.get("/api/v1/integrations/github/status")
def github_status(ctx=Depends(current),db:Session=Depends(get_db)):
 item=db.scalar(select(GitHubInstallation).where(GitHubInstallation.org_id==ctx["org"]))
 return {"connected":bool(item),"account":item.account_login if item else None,"account_type":item.account_type if item else None}
@app.get("/api/v1/integrations/github/repositories")
def github_repositories(ctx=Depends(current),db:Session=Depends(get_db)):
 item=db.scalar(select(GitHubInstallation).where(GitHubInstallation.org_id==ctx["org"]))
 if not item:raise HTTPException(409,"Connect your GitHub account first.")
 token=github_installation_token(item.installation_id);out=[]
 for page in range(1,11):
  result=github_api("/installation/repositories?per_page=100&page="+str(page),token=token)
  repos=result.get("repositories",[]);out.extend(repos)
  if len(repos)<100:break
 return [{"id":r["id"],"full_name":r["full_name"],"name":r["name"],"private":r["private"],"default_branch":r.get("default_branch") or "main","description":r.get("description"),"html_url":r["html_url"],"owner":r["owner"]["login"]} for r in out]
@app.get("/api/v1/integrations/github/repositories/{owner}/{repo}/branches")
def github_branches(owner:str,repo:str,ctx=Depends(current),db:Session=Depends(get_db)):
 if not re.fullmatch(r"[A-Za-z0-9_.-]+",owner) or not re.fullmatch(r"[A-Za-z0-9_.-]+",repo):raise HTTPException(422,"Invalid repository.")
 item=db.scalar(select(GitHubInstallation).where(GitHubInstallation.org_id==ctx["org"]))
 if not item:raise HTTPException(409,"Connect your GitHub account first.")
 token=github_installation_token(item.installation_id)
 data=github_api("/repos/"+urllib.parse.quote(owner,safe="")+"/"+urllib.parse.quote(repo,safe="")+"/branches?per_page=100",token=token)
 return [{"name":b["name"]} for b in data]
class GitHubProjectIn(BaseModel):
 name:str=Field(min_length=1,max_length=120)
 repository_full_name:str
 branch:str=Field(min_length=1,max_length=255)
 framework:str="auto"
@app.post("/api/v1/integrations/github/projects",status_code=201)
def github_import_project(x:GitHubProjectIn,ctx=Depends(current),db:Session=Depends(get_db)):
 if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",x.repository_full_name):raise HTTPException(422,"Invalid repository name.")
 item=db.scalar(select(GitHubInstallation).where(GitHubInstallation.org_id==ctx["org"]))
 if not item:raise HTTPException(409,"Connect your GitHub account first.")
 token=github_installation_token(item.installation_id)
 owner,repo=x.repository_full_name.split("/",1)
 info=github_api("/repos/"+urllib.parse.quote(owner,safe="")+"/"+urllib.parse.quote(repo,safe=""),token=token)
 if info.get("full_name","").lower()!=x.repository_full_name.lower():raise HTTPException(404,"Repository is not available to this GitHub installation.")
 branch=x.branch.strip()
 branches=github_api("/repos/"+urllib.parse.quote(owner,safe="")+"/"+urllib.parse.quote(repo,safe="")+"/branches/"+urllib.parse.quote(branch,safe=""),token=token)
 if not branches.get("name"):raise HTTPException(404,"Selected branch was not found.")
 name=x.name.strip();s=slug(name)
 if db.scalar(select(Project).where(Project.org_id==ctx["org"],Project.slug==s)):s+="-"+secrets.token_hex(2)
 url="https://github.com/"+info["full_name"]
 p=Project(org_id=ctx["org"],name=name,slug=s,framework=x.framework[:60],source_type="github",source_url=url,source_ref=branch)
 db.add(p);db.flush();log(db,ctx,"project.github_imported",info["full_name"]+"@"+branch);db.commit();db.refresh(p)
 return {"id":p.id,"name":p.name,"slug":p.slug,"framework":p.framework,"source_type":p.source_type,"source_url":p.source_url,"source_ref":p.source_ref,"created_at":p.created_at,"deployments":0}
@app.post("/api/v1/webhooks/github")
async def github_webhook(request:Request,db:Session=Depends(get_db)):
 secret_value=os.getenv("GITHUB_WEBHOOK_SECRET","")
 if not secret_value:raise HTTPException(503,"GitHub webhook secret is not configured.")
 body=await request.body()
 signature=request.headers.get("X-Hub-Signature-256","")
 expected="sha256="+hmac.new(secret_value.encode(),body,hashlib.sha256).hexdigest()
 if not hmac.compare_digest(signature,expected):raise HTTPException(401,"Invalid webhook signature.")
 delivery=request.headers.get("X-GitHub-Delivery","")
 event=request.headers.get("X-GitHub-Event","")
 if not delivery:raise HTTPException(400,"Missing GitHub delivery identifier.")
 if db.get(GitHubDelivery,delivery):return {"ok":True,"duplicate":True}
 try:payload=json.loads(body or b"{}")
 except Exception:raise HTTPException(400,"Invalid webhook JSON.")
 db.add(GitHubDelivery(delivery_id=delivery))
 installation_id=(payload.get("installation") or {}).get("id")
 if event=="installation" and payload.get("action")=="deleted" and installation_id:
  installed=db.scalar(select(GitHubInstallation).where(GitHubInstallation.installation_id==installation_id))
  if installed:db.delete(installed)
 elif event=="push" and installation_id and not payload.get("deleted",False):
  installed=db.scalar(select(GitHubInstallation).where(GitHubInstallation.installation_id==installation_id))
  repo=(payload.get("repository") or {}).get("full_name","")
  branch=(payload.get("ref") or "").removeprefix("refs/heads/")
  if installed and repo and branch:
   projects=db.scalars(select(Project).where(Project.org_id==installed.org_id,Project.source_type=="github",Project.source_url=="https://github.com/"+repo)).all()
   for p in projects:
    if (p.source_ref or (payload.get("repository") or {}).get("default_branch") or "main")==branch:
     d=Deployment(org_id=installed.org_id,project_id=p.id,status="queued",source_type="github",source_ref=branch,logs="GitHub push received. Waiting for a registered isolated build worker.")
     db.add(d);db.add(Usage(org_id=installed.org_id,project_id=p.id,metric="deployment_requests",quantity=1))
 db.commit()
 return {"ok":True,"event":event}

@app.get("/api/v1/projects")
def list_projects(ctx=Depends(current),db:Session=Depends(get_db)):
 out=[]
 for p in db.scalars(select(Project).where(Project.org_id==ctx["org"]).order_by(desc(Project.updated_at))):
  n=db.scalar(select(func.count(Deployment.id)).where(Deployment.project_id==p.id))
  out.append({"id":p.id,"name":p.name,"slug":p.slug,"framework":p.framework,"source_type":p.source_type,"source_url":p.source_url,"created_at":p.created_at,"deployments":n})
 return out
@app.post("/api/v1/projects",status_code=201)
def create_project(x:ProjectIn,ctx=Depends(current),db:Session=Depends(get_db)):
 name=x.name.strip()
 if not name:raise HTTPException(422,"Project name required.")
 if x.source_type not in {"manual","github"}:raise HTTPException(422,"Unsupported source type.")
 url=(x.source_url or "").strip()
 if x.source_type=="github" and not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?",url):raise HTTPException(422,"Use a valid public GitHub repository URL.")
 s=slug(name)
 if db.scalar(select(Project).where(Project.org_id==ctx["org"],Project.slug==s)):s+="-"+secrets.token_hex(2)
 p=Project(org_id=ctx["org"],name=name,slug=s,framework=x.framework[:60],source_type=x.source_type,source_url=url or None)
 db.add(p);db.flush();log(db,ctx,"project.created",p.slug);db.commit();db.refresh(p)
 return {"id":p.id,"name":p.name,"slug":p.slug,"framework":p.framework,"source_type":p.source_type,"source_url":p.source_url,"created_at":p.created_at,"deployments":0}
@app.delete("/api/v1/projects/{pid}",status_code=204)
def delete_project(pid:int,ctx=Depends(current),db:Session=Depends(get_db)):
 p=project(db,ctx,pid);log(db,ctx,"project.deleted",p.slug);db.delete(p);db.commit()
def queue(db,ctx,p,typ,ref):
 d=Deployment(org_id=ctx["org"],project_id=p.id,status="queued",source_type=typ,source_ref=ref,logs="Deployment queued. Waiting for a registered isolated build worker.")
 db.add(d);db.add(Usage(org_id=ctx["org"],project_id=p.id,metric="deployment_requests",quantity=1));return d
@app.get("/api/v1/projects/{pid}/deployments")
def list_deployments(pid:int,ctx=Depends(current),db:Session=Depends(get_db)):
 project(db,ctx,pid);return [dep_dict(d) for d in db.scalars(select(Deployment).where(Deployment.project_id==pid,Deployment.org_id==ctx["org"]).order_by(desc(Deployment.created_at)))]
@app.post("/api/v1/projects/{pid}/deployments",status_code=202)
def deploy(pid:int,ctx=Depends(current),db:Session=Depends(get_db)):
 p=project(db,ctx,pid)
 if not p.source_url:raise HTTPException(422,"Connect a GitHub repository or upload a ZIP first.")
 d=queue(db,ctx,p,"github",p.source_ref or p.source_url);log(db,ctx,"deployment.queued",d.uid);db.commit();db.refresh(d);return dep_dict(d)
@app.post("/api/v1/projects/{pid}/source/zip",status_code=202)
async def upload(pid:int,source:UploadFile=File(...),ctx=Depends(current),db:Session=Depends(get_db)):
 p=project(db,ctx,pid);limit=int(os.getenv("MAX_UPLOAD_MB","25"))*1024*1024
 if not source.filename or not source.filename.lower().endswith(".zip"):raise HTTPException(415,"Upload a ZIP archive.")
 data=await source.read(limit+1)
 if len(data)>limit:raise HTTPException(413,"ZIP exceeds upload limit.")
 try:
  with zipfile.ZipFile(io.BytesIO(data)) as z:
   entries=z.infolist()
   if len(entries)>3000:raise HTTPException(413,"Too many archive entries.")
   total=0
   for f in entries:
    q=PurePosixPath(f.filename);total+=f.file_size
    if q.is_absolute() or ".." in q.parts or f.file_size>100*1024*1024 or total>500*1024*1024:raise HTTPException(400,"Unsafe or oversized archive.")
 except zipfile.BadZipFile:raise HTTPException(400,"Invalid ZIP archive.")
 folder=Path(os.getenv("UPLOAD_DIR","/var/data/higlowcloud/uploads"));folder.mkdir(parents=True,exist_ok=True)
 key=secrets.token_hex(20)+".zip";(folder/key).write_bytes(data)
 d=queue(db,ctx,p,"zip",key);d.logs="ZIP validated and stored. Waiting for an isolated build worker.";log(db,ctx,"source.uploaded",p.slug);db.commit();db.refresh(d);return dep_dict(d)
@app.post("/api/v1/deployments/{did}/cancel")
def cancel(did:int,ctx=Depends(current),db:Session=Depends(get_db)):
 d=db.scalar(select(Deployment).where(Deployment.id==did,Deployment.org_id==ctx["org"]))
 if not d:raise HTTPException(404,"Deployment not found.")
 if d.status not in {"queued","building"}:raise HTTPException(409,"Deployment cannot be cancelled.")
 d.status="cancelled";d.finished_at=now();d.logs+="\nCancelled by user.";db.commit();return dep_dict(d)
@app.post("/api/v1/deployments/{did}/redeploy",status_code=202)
def redeploy(did:int,ctx=Depends(current),db:Session=Depends(get_db)):
 old=db.scalar(select(Deployment).where(Deployment.id==did,Deployment.org_id==ctx["org"]))
 if not old:raise HTTPException(404,"Deployment not found.")
 p=project(db,ctx,old.project_id);d=queue(db,ctx,p,old.source_type,old.source_ref);db.commit();db.refresh(d);return dep_dict(d)
@app.get("/api/v1/deployments/{did}/logs")
def logs(did:int,ctx=Depends(current),db:Session=Depends(get_db)):
 d=db.scalar(select(Deployment).where(Deployment.id==did,Deployment.org_id==ctx["org"]))
 if not d:raise HTTPException(404,"Deployment not found.")
 return {"status":d.status,"logs":d.logs}
@app.get("/api/v1/projects/{pid}/env")
def env_list(pid:int,ctx=Depends(current),db:Session=Depends(get_db)):
 project(db,ctx,pid);return [{"id":v.id,"key":v.key,"secret":v.secret,"value":None if v.secret else dec(v.value_enc),"updated_at":v.updated_at} for v in db.scalars(select(EnvVar).where(EnvVar.project_id==pid,EnvVar.org_id==ctx["org"]))]
class EnvIn(BaseModel):key:str=Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,179}$");value:str=Field(max_length=10000);secret:bool=True
@app.put("/api/v1/projects/{pid}/env")
def env_put(pid:int,x:EnvIn,ctx=Depends(current),db:Session=Depends(get_db)):
 project(db,ctx,pid);v=db.scalar(select(EnvVar).where(EnvVar.project_id==pid,EnvVar.org_id==ctx["org"],EnvVar.key==x.key))
 if v:v.value_enc=enc(x.value);v.secret=x.secret
 else:db.add(EnvVar(org_id=ctx["org"],project_id=pid,key=x.key,value_enc=enc(x.value),secret=x.secret))
 log(db,ctx,"env.updated",x.key);db.commit();return {"ok":True,"key":x.key}
@app.delete("/api/v1/projects/{pid}/env/{key}",status_code=204)
def env_delete(pid:int,key:str,ctx=Depends(current),db:Session=Depends(get_db)):
 project(db,ctx,pid);v=db.scalar(select(EnvVar).where(EnvVar.project_id==pid,EnvVar.org_id==ctx["org"],EnvVar.key==key))
 if v:db.delete(v);db.commit()
@app.get("/api/v1/projects/{pid}/domains")
def domains(pid:int,ctx=Depends(current),db:Session=Depends(get_db)):
 project(db,ctx,pid);return [{"id":d.id,"hostname":d.hostname,"status":d.status,"verification_token":d.token} for d in db.scalars(select(Domain).where(Domain.project_id==pid,Domain.org_id==ctx["org"]))]
@app.post("/api/v1/projects/{pid}/domains",status_code=201)
def add_domain(pid:int,x:DomainIn,ctx=Depends(current),db:Session=Depends(get_db)):
 project(db,ctx,pid);host=x.hostname.lower().strip().rstrip(".")
 if not re.fullmatch(r"(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(\.([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))+",host):raise HTTPException(422,"Invalid hostname.")
 if db.scalar(select(Domain).where(Domain.hostname==host)):raise HTTPException(409,"Domain already registered.")
 d=Domain(org_id=ctx["org"],project_id=pid,hostname=host);db.add(d);db.commit();db.refresh(d);return {"id":d.id,"hostname":d.hostname,"status":d.status,"verification_token":d.token}
@app.delete("/api/v1/domains/{did}",status_code=204)
def domain_delete(did:int,ctx=Depends(current),db:Session=Depends(get_db)):
 d=db.scalar(select(Domain).where(Domain.id==did,Domain.org_id==ctx["org"]))
 if d:db.delete(d);db.commit()
@app.get("/api/v1/projects/{pid}/databases")
def db_list(pid:int,ctx=Depends(current),db:Session=Depends(get_db)):
 project(db,ctx,pid);return [{"id":d.id,"name":d.name,"engine":d.engine,"status":d.status} for d in db.scalars(select(DatabaseResource).where(DatabaseResource.project_id==pid,DatabaseResource.org_id==ctx["org"]))]
@app.post("/api/v1/projects/{pid}/databases",status_code=202)
def db_create(pid:int,x:DbIn,ctx=Depends(current),db:Session=Depends(get_db)):
 project(db,ctx,pid)
 if x.engine not in {"postgres","redis"}:raise HTTPException(422,"Engine must be postgres or redis.")
 d=DatabaseResource(org_id=ctx["org"],project_id=pid,name=x.name.strip(),engine=x.engine);db.add(d);db.commit();db.refresh(d);return {"id":d.id,"name":d.name,"engine":d.engine,"status":d.status,"note":"Request stored; connect a database provisioner to create the instance."}
@app.get("/api/v1/usage")
def usage(ctx=Depends(current),db:Session=Depends(get_db)):
 events=db.scalars(select(Usage).where(Usage.org_id==ctx["org"]).order_by(desc(Usage.created_at)).limit(200)).all();totals={}
 for e in events:totals[e.metric]=totals.get(e.metric,0)+e.quantity
 return {"totals":totals,"events":[{"metric":e.metric,"quantity":e.quantity,"created_at":e.created_at} for e in events]}
@app.get("/api/v1/audit")
def audit_list(ctx=Depends(current),db:Session=Depends(get_db)):
 return [{"action":a.action,"target":a.target,"created_at":a.created_at} for a in db.scalars(select(Audit).where(Audit.org_id==ctx["org"]).order_by(desc(Audit.created_at)).limit(100))]
@app.get("/api/v1/admin/overview")
def admin_overview(ctx=Depends(platform_admin),db:Session=Depends(get_db)):
 return {"users":db.query(User).count(),"workspaces":db.query(Organization).count(),"projects":db.query(Project).count(),"deployments":db.query(Deployment).count(),"queued":db.query(Deployment).filter(Deployment.status=="queued").count(),"workers":"not connected","runtime":"not connected"}
@app.get("/api/v1/admin/users")
def admin_users(ctx=Depends(platform_admin),db:Session=Depends(get_db)):
 return [{"id":u.id,"email":u.email,"name":u.name,"active":u.active,"admin":u.admin,"created_at":u.created_at} for u in db.scalars(select(User).order_by(desc(User.created_at)).limit(500))]
@app.get("/api/v1/admin/deployments")
def admin_deployments(ctx=Depends(platform_admin),db:Session=Depends(get_db)):
 return [dep_dict(d) for d in db.scalars(select(Deployment).order_by(desc(Deployment.created_at)).limit(200))]
@app.post("/api/v1/admin/users/{uid}/disable")
def disable(uid:int,ctx=Depends(platform_admin),db:Session=Depends(get_db)):
 u=db.get(User,uid)
 if not u:raise HTTPException(404,"User not found.")
 if u.id==ctx["user"].id:raise HTTPException(400,"Cannot disable your own account.")
 u.active=False;db.commit();return {"ok":True}
