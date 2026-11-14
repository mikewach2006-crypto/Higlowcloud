from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, and_, or_, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, SessionLocal, engine, get_db

UTC = timezone.utc

def utcnow() -> datetime:
    return datetime.now(UTC)

class CallContact(Base):
    __tablename__ = "nenva_call_contacts"
    __table_args__ = (UniqueConstraint("user_id", "contact_user_id", name="uq_nenva_call_contact"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    contact_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class CallSocketTicket(Base):
    __tablename__ = "nenva_call_socket_tickets"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class CallMessage(Base):
    __tablename__ = "nenva_call_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/api/v1/nenva-call", tags=["Nenva Call"])
bearer = HTTPBearer(auto_error=False)

def require_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    if not credentials:
        raise HTTPException(401, "Sign in to Nenva Call.")
    from .main import token_data, User
    claims = token_data(credentials.credentials)
    user = db.get(User, int(claims["sub"]))
    if not user or not user.active:
        raise HTTPException(401, "Your account is unavailable.")
    return user

class ContactIn(BaseModel):
    user_id: int

class MessageIn(BaseModel):
    recipient_id: int
    body: str = Field(min_length=1, max_length=5000)

class SignalManager:
    def __init__(self):
        self.connections: dict[int, set[WebSocket]] = {}
        self.lock = asyncio.Lock()

    async def connect(self, user_id: int, socket: WebSocket):
        await socket.accept()
        async with self.lock:
            self.connections.setdefault(user_id, set()).add(socket)

    async def disconnect(self, user_id: int, socket: WebSocket):
        async with self.lock:
            sockets = self.connections.get(user_id, set())
            sockets.discard(socket)
            if not sockets:
                self.connections.pop(user_id, None)

    async def send_user(self, user_id: int, payload: dict[str, Any]):
        async with self.lock:
            sockets = list(self.connections.get(user_id, set()))
        for socket in sockets:
            try:
                await socket.send_json(payload)
            except Exception:
                await self.disconnect(user_id, socket)

    def online(self, user_id: int) -> bool:
        return bool(self.connections.get(user_id))

signal = SignalManager()

def is_contact(db: Session, a: int, b: int) -> bool:
    return db.scalar(select(CallContact.id).where(
        or_(
            and_(CallContact.user_id == a, CallContact.contact_user_id == b),
            and_(CallContact.user_id == b, CallContact.contact_user_id == a),
        )
    )) is not None

def user_card(user, online: bool = False):
    return {"id": user.id, "name": user.name or user.email.split("@")[0],
            "email": user.email, "online": online}

@router.post("/socket-ticket")
def create_socket_ticket(user=Depends(require_user), db: Session = Depends(get_db)):
    raw = secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    db.add(CallSocketTicket(id=digest, user_id=user.id, expires_at=utcnow() + timedelta(minutes=2)))
    db.commit()
    return {"ticket": raw, "expires_in": 120}

@router.get("/config")
def call_config(user=Depends(require_user)):
    ice_servers: list[dict[str, Any]] = [{"urls": ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"]}]
    turn_urls = [x.strip() for x in os.getenv("NENVA_TURN_URLS", "").split(",") if x.strip()]
    turn_user = os.getenv("NENVA_TURN_USERNAME", "").strip()
    turn_credential = os.getenv("NENVA_TURN_CREDENTIAL", "").strip()
    if turn_urls and turn_user and turn_credential:
        ice_servers.append({"urls": turn_urls, "username": turn_user, "credential": turn_credential})
    return {"user": {"id": user.id, "name": user.name, "email": user.email},
            "ice_servers": ice_servers,
            "turn_configured": len(ice_servers) > 1,
            "features": {"messages": True, "audio_calls": True, "video_calls": True}}

@router.get("/contacts/search")
def search_contacts(q: str = "", user=Depends(require_user), db: Session = Depends(get_db)):
    from .main import User
    query = q.strip().lower()
    if len(query) < 2:
        return []
    rows = db.scalars(select(User).where(
        User.id != user.id, User.active.is_(True),
        or_(User.email.ilike("%" + query + "%"), User.name.ilike("%" + query + "%"))
    ).order_by(User.name, User.email).limit(20)).all()
    return [{**user_card(row, signal.online(row.id)), "is_contact": is_contact(db, user.id, row.id)} for row in rows]

@router.get("/contacts")
def list_contacts(user=Depends(require_user), db: Session = Depends(get_db)):
    from .main import User
    ids = db.scalars(select(CallContact.contact_user_id).where(CallContact.user_id == user.id)).all()
    rows = db.scalars(select(User).where(User.id.in_(ids), User.active.is_(True)).order_by(User.name, User.email)).all() if ids else []
    return [user_card(row, signal.online(row.id)) for row in rows]

@router.post("/contacts", status_code=201)
def add_contact(x: ContactIn, user=Depends(require_user), db: Session = Depends(get_db)):
    from .main import User
    other = db.get(User, x.user_id)
    if not other or not other.active or other.id == user.id:
        raise HTTPException(404, "Nenva Call user not found.")
    if not is_contact(db, user.id, other.id):
        db.add_all([
            CallContact(user_id=user.id, contact_user_id=other.id),
            CallContact(user_id=other.id, contact_user_id=user.id),
        ])
        db.commit()
    return user_card(other, signal.online(other.id))

@router.get("/conversations")
def conversations(user=Depends(require_user), db: Session = Depends(get_db)):
    from .main import User
    rows = db.scalars(select(CallMessage).where(
        or_(CallMessage.sender_id == user.id, CallMessage.recipient_id == user.id)
    ).order_by(CallMessage.created_at.desc()).limit(500)).all()
    latest: dict[int, CallMessage] = {}
    for item in rows:
        peer_id = item.recipient_id if item.sender_id == user.id else item.sender_id
        latest.setdefault(peer_id, item)
    peers = db.scalars(select(User).where(User.id.in_(list(latest.keys())))).all() if latest else []
    by_id = {p.id: p for p in peers}
    result = []
    for peer_id, item in latest.items():
        peer = by_id.get(peer_id)
        if peer:
            result.append({"contact": user_card(peer, signal.online(peer_id)),
                           "last_message": {"id": item.id, "body": item.body,
                            "sender_id": item.sender_id, "created_at": item.created_at,
                            "read": item.read_at is not None}})
    return result

@router.get("/messages/{peer_id}")
def get_messages(peer_id: int, limit: int = 100, user=Depends(require_user), db: Session = Depends(get_db)):
    if peer_id == user.id or not is_contact(db, user.id, peer_id):
        raise HTTPException(403, "Add this person as a contact first.")
    rows = db.scalars(select(CallMessage).where(
        or_(
            and_(CallMessage.sender_id == user.id, CallMessage.recipient_id == peer_id),
            and_(CallMessage.sender_id == peer_id, CallMessage.recipient_id == user.id),
        )
    ).order_by(CallMessage.created_at.desc()).limit(max(1, min(limit, 200)))).all()
    for item in rows:
        if item.recipient_id == user.id and item.read_at is None:
            item.read_at = utcnow()
    db.commit()
    return [{"id": x.id, "sender_id": x.sender_id, "recipient_id": x.recipient_id,
             "body": x.body, "created_at": x.created_at, "read": x.read_at is not None}
            for x in reversed(rows)]

@router.post("/messages", status_code=201)
async def send_message(x: MessageIn, user=Depends(require_user), db: Session = Depends(get_db)):
    from .main import User
    recipient = db.get(User, x.recipient_id)
    if not recipient or not recipient.active or recipient.id == user.id or not is_contact(db, user.id, recipient.id):
        raise HTTPException(403, "Add this person as a contact before messaging.")
    body = x.body.strip()
    if not body:
        raise HTTPException(422, "Message cannot be empty.")
    item = CallMessage(sender_id=user.id, recipient_id=recipient.id, body=body)
    db.add(item)
    db.commit()
    db.refresh(item)
    payload = {"type": "message", "message": {"id": item.id, "sender_id": item.sender_id,
        "recipient_id": item.recipient_id, "body": item.body, "created_at": item.created_at}}
    await signal.send_user(recipient.id, payload)
    return payload["message"]

@router.websocket("/ws")
async def call_socket(socket: WebSocket, ticket: str = ""):
    from .main import User
    db = SessionLocal()
    user = None
    try:
        digest = hashlib.sha256(ticket.encode()).hexdigest() if ticket else ""
        saved = db.get(CallSocketTicket, digest)
        if not saved or saved.expires_at.replace(tzinfo=UTC) < utcnow():
            await socket.close(code=4401)
            db.close()
            return
        user = db.get(User, saved.user_id)
        db.delete(saved)
        db.commit()
        if not user or not user.active:
            await socket.close(code=4401)
            db.close()
            return
    except Exception:
        await socket.close(code=4401)
        db.close()
        return
    await signal.connect(user.id, socket)
    try:
        await socket.send_json({"type": "ready", "user_id": user.id})
        contacts = db.scalars(select(CallContact.contact_user_id).where(CallContact.user_id == user.id)).all()
        for peer_id in contacts:
            await signal.send_user(peer_id, {"type": "presence", "user_id": user.id, "online": True})
        while True:
            event = await socket.receive_json()
            kind = event.get("type")
            if kind == "ping":
                await socket.send_json({"type": "pong"})
                continue
            if kind not in {"call", "offer", "answer", "ice", "hangup", "decline", "typing"}:
                await socket.send_json({"type": "error", "message": "Unsupported call event."})
                continue
            try:
                peer_id = int(event.get("to"))
            except (TypeError, ValueError):
                await socket.send_json({"type": "error", "message": "Invalid recipient."})
                continue
            if peer_id == user.id or not is_contact(db, user.id, peer_id):
                await socket.send_json({"type": "error", "message": "Recipient is not in your contacts."})
                continue
            await signal.send_user(peer_id, {"type": kind, "from_id": user.id,
                "from_name": user.name or user.email.split("@")[0],
                "data": event.get("data") if isinstance(event.get("data"), dict) else {}})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await signal.disconnect(user.id, socket)
        contacts = db.scalars(select(CallContact.contact_user_id).where(CallContact.user_id == user.id)).all()
        if not signal.online(user.id):
            for peer_id in contacts:
                await signal.send_user(peer_id, {"type": "presence", "user_id": user.id, "online": False})
        db.close()
