from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select, or_, and_
from sqlalchemy.orm import Mapped, mapped_column, Session

from .database import Base, engine, get_db
from .main import SECRET, now, pw_hash, pw_check

router = APIRouter(prefix="/api/v1/nenva-call", tags=["Nenva Call"])
bearer = HTTPBearer(auto_error=False)
UTC = timezone.utc


class CallUser(Base):
    __tablename__ = "nenva_call_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    verification_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CallConversation(Base):
    __tablename__ = "nenva_call_conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pair_key: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CallParticipant(Base):
    __tablename__ = "nenva_call_participants"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("nenva_call_conversations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("nenva_call_users.id", ondelete="CASCADE"), index=True)
    __table_args__ = (UniqueConstraint("conversation_id", "user_id"),)


class CallMessage(Base):
    __tablename__ = "nenva_call_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("nenva_call_conversations.id", ondelete="CASCADE"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("nenva_call_users.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class CallSession(Base):
    __tablename__ = "nenva_call_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: __import__("uuid").uuid4().__str__())
    caller_id: Mapped[int] = mapped_column(ForeignKey("nenva_call_users.id", ondelete="CASCADE"), index=True)
    receiver_id: Mapped[int] = mapped_column(ForeignKey("nenva_call_users.id", ondelete="CASCADE"), index=True)
    media: Mapped[str] = mapped_column(String(12), default="audio")
    status: Mapped[str] = mapped_column(String(16), default="ringing", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class CallSignal(Base):
    __tablename__ = "nenva_call_signals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("nenva_call_sessions.id", ondelete="CASCADE"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("nenva_call_users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


Base.metadata.create_all(bind=engine)


def _code_hash(code: str) -> str:
    return hmac.new(SECRET, ("nenva-call-verify:" + code).encode(), hashlib.sha256).hexdigest()


def _send_email(to: str, code: str) -> None:
    host = os.getenv("SMTP_HOST", "").strip()
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    sender = os.getenv("SMTP_FROM", user).strip()
    if not host or not sender:
        raise HTTPException(503, "Email verification is not configured. Set SMTP_HOST, SMTP_FROM and SMTP credentials in HiglowCloud.")
    message = EmailMessage()
    message["Subject"] = "Your Nenva Call verification code"
    message["From"] = sender
    message["To"] = to
    message.set_content("Your Nenva Call verification code is " + code + ". It expires in 10 minutes. If you did not request this, ignore this email.")
    port = int(os.getenv("SMTP_PORT", "587"))
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15) as server:
                if user: server.login(user, password)
                server.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.starttls()
                if user: server.login(user, password)
                server.send_message(message)
    except Exception:
        raise HTTPException(502, "We could not send the verification email. Check the HiglowCloud SMTP settings.")


def _send_sms(phone: str, code: str) -> None:
    username = os.getenv("AT_USERNAME", "").strip()
    api_key = os.getenv("AT_API_KEY", "").strip()
    sender_id = os.getenv("AT_SENDER_ID", "").strip()
    if not username or not api_key:
        raise HTTPException(503, "Phone verification is not configured. Set AT_USERNAME and AT_API_KEY in HiglowCloud.")
    url = os.getenv("AT_SMS_URL", "https://api.africastalking.com/version1/messaging")
    body = urllib.parse.urlencode({"username": username, "to": phone, "message": "Your Nenva Call verification code is " + code + ". It expires in 10 minutes."})
    headers = {"apiKey": api_key, "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
    if sender_id: body += "&from=" + urllib.parse.quote_plus(sender_id)
    req = urllib.request.Request(url, data=body.encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            result = json.loads(response.read().decode() or "{}")
        recipients = ((result.get("SMSMessageData") or {}).get("Recipients") or [])
        if not recipients or recipients[0].get("status") not in {"Success", "Queued"}:
            raise ValueError("SMS provider rejected the message")
    except Exception:
        raise HTTPException(502, "We could not send the verification SMS. Check the HiglowCloud Africa's Talking settings.")


def _token(user_id: int) -> str:
    head = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    payload = secrets.token_urlsafe(1)  # replaced below with a deterministic JWT payload
    import base64
    payload = base64.urlsafe_b64encode(json.dumps({"sub": user_id, "exp": int(time.time()) + 86400}).encode()).rstrip(b"=").decode()
    body = head + "." + payload
    signature = base64.urlsafe_b64encode(hmac.new(SECRET, body.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    return body + "." + signature


def _identity(credentials: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)) -> CallUser:
    if not credentials:
        raise HTTPException(401, "Sign in to Nenva Call.")
    try:
        import base64
        head, payload, signature = credentials.credentials.split(".")
        body = head + "." + payload
        expected = base64.urlsafe_b64encode(hmac.new(SECRET, body.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
        if not hmac.compare_digest(expected, signature):
            raise ValueError()
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * ((4 - len(payload) % 4) % 4)))
        if int(data["exp"]) < int(time.time()):
            raise ValueError()
        user = db.get(CallUser, int(data["sub"]))
        if not user or not user.active:
            raise ValueError()
        return user
    except Exception:
        raise HTTPException(401, "Nenva Call session expired. Sign in again.")


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=255)
    phone: str = Field(min_length=8, max_length=24)
    password: str = Field(min_length=10, max_length=128)


class VerifyIn(BaseModel):
    email: str
    code: str = Field(pattern=r"^\d{6}$")
    channel: str = Field(pattern=r"^(email|phone)$")


class LoginIn(BaseModel):
    email: str
    password: str


class ContactIn(BaseModel):
    email_or_phone: str = Field(min_length=3, max_length=255)


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=8000)


class CallIn(BaseModel):
    receiver_id: int
    media: str = Field(pattern=r"^(audio|video)$")


class SignalIn(BaseModel):
    kind: str = Field(pattern=r"^(offer|answer|ice|hangup|reject)$")
    payload: dict = Field(default_factory=dict)


@router.get("/health")
def health():
    return {"service": "nenva-call-cloud", "status": "ok", "messaging": "database-backed", "signalling": "database-backed"}


@router.get("/config")
def client_config():
    urls = [x.strip() for x in os.getenv("TURN_URLS", "stun:stun.l.google.com:19302").split(",") if x.strip()]
    servers = [{"urls": url} for url in urls]
    username, credential = os.getenv("TURN_USERNAME", ""), os.getenv("TURN_CREDENTIAL", "")
    if username and credential and any(url.startswith("turn:") or url.startswith("turns:") for url in urls):
        for server in servers:
            server["username"] = username
            server["credential"] = credential
    return {"api": "/api/v1/nenva-call", "ice_servers": servers, "poll_interval_ms": 1500, "features": {"audio_calls": True, "video_calls": True, "messages": True}}


@router.post("/auth/register", status_code=201)
def register(x: RegisterIn, db: Session = Depends(get_db)):
    email = x.email.strip().lower()
    phone = x.phone.strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(422, "Enter a valid email address.")
    if not re.fullmatch(r"\+[1-9]\d{7,14}", phone):
        raise HTTPException(422, "Enter your phone number in international format, for example +2547XXXXXXXX.")
    if db.scalar(select(CallUser).where(or_(CallUser.email == email, CallUser.phone == phone))):
        raise HTTPException(409, "That email address or phone number is already registered.")
    code = f"{secrets.randbelow(1000000):06d}"
    user = CallUser(name=x.name.strip(), email=email, phone=phone, password_hash=pw_hash(x.password),
                    verification_hash=_code_hash(code), verification_expires_at=now() + timedelta(minutes=10))
    db.add(user)
    db.flush()
    try:
        _send_email(email, code)
        _send_sms(phone, code)
    except Exception:
        db.rollback()
        raise
    db.commit()
    return {"ok": True, "verification_required": ["email", "phone"], "message": "Verification codes sent to your email and phone."}


@router.post("/auth/verify")
def verify(x: VerifyIn, db: Session = Depends(get_db)):
    user = db.scalar(select(CallUser).where(CallUser.email == x.email.strip().lower()))
    if not user or not user.verification_hash or not user.verification_expires_at:
        raise HTTPException(400, "No active verification request was found.")
    expiry = user.verification_expires_at
    if expiry.tzinfo is None: expiry = expiry.replace(tzinfo=UTC)
    if expiry < now() or not hmac.compare_digest(user.verification_hash, _code_hash(x.code)):
        raise HTTPException(400, "The verification code is invalid or expired. Register again to request a new code.")
    if x.channel == "email": user.email_verified = True
    else: user.phone_verified = True
    if user.email_verified and user.phone_verified:
        user.verification_hash = None
        user.verification_expires_at = None
    db.commit()
    return {"ok": True, "email_verified": user.email_verified, "phone_verified": user.phone_verified,
            "access_token": _token(user.id) if user.email_verified and user.phone_verified else None}


@router.post("/auth/login")
def login(x: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(CallUser).where(CallUser.email == x.email.strip().lower()))
    if not user or not pw_check(x.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect.")
    if not user.active: raise HTTPException(403, "This Nenva Call account is disabled.")
    if not user.email_verified or not user.phone_verified:
        raise HTTPException(403, "Verify both your email address and phone number before signing in.")
    return {"access_token": _token(user.id), "token_type": "bearer", "user": {"id": user.id, "name": user.name, "email": user.email, "phone": user.phone}}


@router.get("/auth/me")
def me(user: CallUser = Depends(_identity)):
    return {"id": user.id, "name": user.name, "email": user.email, "phone": user.phone,
            "email_verified": user.email_verified, "phone_verified": user.phone_verified}


@router.get("/contacts")
def contacts(user: CallUser = Depends(_identity), db: Session = Depends(get_db)):
    rows = db.execute(select(CallParticipant, CallConversation).join(CallConversation, CallParticipant.conversation_id == CallConversation.id)
                      .where(CallParticipant.user_id == user.id)).all()
    result = []
    for participant, conversation in rows:
        other = db.scalar(select(CallParticipant).where(CallParticipant.conversation_id == conversation.id, CallParticipant.user_id != user.id))
        if not other: continue
        contact = db.get(CallUser, other.user_id)
        if contact:
            last = db.scalar(select(CallMessage).where(CallMessage.conversation_id == conversation.id).order_by(CallMessage.id.desc()).limit(1))
            result.append({"conversation_id": conversation.id, "contact": {"id": contact.id, "name": contact.name, "email": contact.email},
                           "last_message": last.body if last else None, "last_message_at": last.created_at if last else None})
    return result


@router.post("/contacts", status_code=201)
def add_contact(x: ContactIn, user: CallUser = Depends(_identity), db: Session = Depends(get_db)):
    value = x.email_or_phone.strip().lower()
    other = db.scalar(select(CallUser).where(or_(CallUser.email == value, CallUser.phone == x.email_or_phone.strip())))
    if not other or not other.email_verified or not other.phone_verified:
        raise HTTPException(404, "Nenva Call user not found.")
    if other.id == user.id: raise HTTPException(422, "You cannot add yourself.")
    pair = ":".join(map(str, sorted([user.id, other.id])))
    conversation = db.scalar(select(CallConversation).where(CallConversation.pair_key == pair))
    if not conversation:
        conversation = CallConversation(pair_key=pair)
        db.add(conversation)
        db.flush()
        db.add_all([CallParticipant(conversation_id=conversation.id, user_id=user.id), CallParticipant(conversation_id=conversation.id, user_id=other.id)])
        db.commit()
    return {"conversation_id": conversation.id, "contact": {"id": other.id, "name": other.name, "email": other.email}}


def _participant(conversation_id: int, user_id: int, db: Session):
    item = db.scalar(select(CallParticipant).where(CallParticipant.conversation_id == conversation_id, CallParticipant.user_id == user_id))
    if not item: raise HTTPException(404, "Conversation not found.")
    return item


@router.get("/conversations/{conversation_id}/messages")
def list_messages(conversation_id: int, after_id: int = 0, user: CallUser = Depends(_identity), db: Session = Depends(get_db)):
    _participant(conversation_id, user.id, db)
    rows = db.scalars(select(CallMessage).where(CallMessage.conversation_id == conversation_id, CallMessage.id > after_id)
                      .order_by(CallMessage.id.asc()).limit(200)).all()
    return [{"id": m.id, "sender_id": m.sender_id, "body": m.body, "created_at": m.created_at} for m in rows]


@router.post("/conversations/{conversation_id}/messages", status_code=201)
def send_message(conversation_id: int, x: MessageIn, user: CallUser = Depends(_identity), db: Session = Depends(get_db)):
    _participant(conversation_id, user.id, db)
    message = CallMessage(conversation_id=conversation_id, sender_id=user.id, body=x.body.strip())
    db.add(message)
    db.commit()
    db.refresh(message)
    return {"id": message.id, "conversation_id": conversation_id, "sender_id": user.id, "body": message.body, "created_at": message.created_at}


@router.post("/calls", status_code=201)
def start_call(x: CallIn, user: CallUser = Depends(_identity), db: Session = Depends(get_db)):
    receiver = db.get(CallUser, x.receiver_id)
    if not receiver or not receiver.active or not receiver.email_verified or not receiver.phone_verified:
        raise HTTPException(404, "The person you are calling is not available on Nenva Call.")
    if receiver.id == user.id: raise HTTPException(422, "You cannot call yourself.")
    active = db.scalar(select(CallSession).where(or_(and_(CallSession.caller_id == user.id, CallSession.receiver_id == receiver.id),
                                                       and_(CallSession.caller_id == receiver.id, CallSession.receiver_id == user.id)),
                                          CallSession.status.in_(["ringing", "active"])))
    if active: raise HTTPException(409, "There is already an active call between these users.")
    call = CallSession(caller_id=user.id, receiver_id=receiver.id, media=x.media, status="ringing")
    db.add(call)
    db.commit()
    return {"id": call.id, "status": call.status, "media": call.media, "receiver_id": receiver.id}


@router.get("/calls/incoming")
def incoming_calls(user: CallUser = Depends(_identity), db: Session = Depends(get_db)):
    rows = db.scalars(select(CallSession).where(CallSession.receiver_id == user.id, CallSession.status == "ringing")
                      .order_by(CallSession.created_at.desc()).limit(20)).all()
    return [{"id": c.id, "caller": {"id": c.caller_id, "name": db.get(CallUser, c.caller_id).name}, "media": c.media, "created_at": c.created_at} for c in rows]


@router.post("/calls/{call_id}/accept")
def accept_call(call_id: str, user: CallUser = Depends(_identity), db: Session = Depends(get_db)):
    call = db.get(CallSession, call_id)
    if not call or call.receiver_id != user.id: raise HTTPException(404, "Incoming call not found.")
    if call.status != "ringing": raise HTTPException(409, "This call is no longer ringing.")
    call.status = "active"
    call.answered_at = now()
    db.commit()
    return {"id": call.id, "status": call.status, "media": call.media}


@router.post("/calls/{call_id}/signals", status_code=201)
def send_signal(call_id: str, x: SignalIn, user: CallUser = Depends(_identity), db: Session = Depends(get_db)):
    call = db.get(CallSession, call_id)
    if not call or user.id not in {call.caller_id, call.receiver_id}: raise HTTPException(404, "Call not found.")
    if call.status not in {"ringing", "active"} and x.kind != "hangup": raise HTTPException(409, "Call has ended.")
    payload = json.dumps(x.payload, separators=(",", ":"))
    if len(payload) > 200000: raise HTTPException(413, "Call signal is too large.")
    signal = CallSignal(call_id=call_id, sender_id=user.id, kind=x.kind, payload=payload)
    db.add(signal)
    if x.kind in {"hangup", "reject"}:
        call.status = "ended"
        call.ended_at = now()
    db.commit()
    db.refresh(signal)
    return {"id": signal.id, "ok": True}


@router.get("/calls/{call_id}/signals")
def poll_signals(call_id: str, after_id: int = 0, user: CallUser = Depends(_identity), db: Session = Depends(get_db)):
    call = db.get(CallSession, call_id)
    if not call or user.id not in {call.caller_id, call.receiver_id}: raise HTTPException(404, "Call not found.")
    rows = db.scalars(select(CallSignal).where(CallSignal.call_id == call_id, CallSignal.sender_id != user.id, CallSignal.id > after_id)
                      .order_by(CallSignal.id.asc()).limit(100)).all()
    return {"status": call.status, "signals": [{"id": s.id, "sender_id": s.sender_id, "kind": s.kind, "payload": json.loads(s.payload), "created_at": s.created_at} for s in rows]}


@router.post("/calls/{call_id}/end")
def end_call(call_id: str, user: CallUser = Depends(_identity), db: Session = Depends(get_db)):
    call = db.get(CallSession, call_id)
    if not call or user.id not in {call.caller_id, call.receiver_id}: raise HTTPException(404, "Call not found.")
    if call.status != "ended":
        call.status = "ended"
        call.ended_at = now()
        db.add(CallSignal(call_id=call_id, sender_id=user.id, kind="hangup", payload="{}"))
        db.commit()
    return {"id": call_id, "status": "ended"}


@router.get("/calls/history")
def call_history(user: CallUser = Depends(_identity), db: Session = Depends(get_db)):
    rows = db.scalars(select(CallSession).where(or_(CallSession.caller_id == user.id, CallSession.receiver_id == user.id))
                      .order_by(CallSession.created_at.desc()).limit(100)).all()
    return [{"id": c.id, "caller_id": c.caller_id, "receiver_id": c.receiver_id, "media": c.media,
             "status": c.status, "created_at": c.created_at, "ended_at": c.ended_at} for c in rows]
