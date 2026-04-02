import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


def _uuid():
    return str(uuid.uuid4())


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    avatar_path = Column(String, nullable=True)
    voice_embedding = Column(JSON, nullable=True)  # list[float] 256-dim
    preferences = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversations = relationship("Conversation", back_populates="profile")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=_uuid)
    profile_id = Column(String, ForeignKey("user_profiles.id"), nullable=True)
    title = Column(String, default="New Conversation")
    model = Column(String, default="qwen2.5:9b")
    system_prompt = Column(Text, default="You are a helpful assistant.")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    messages = relationship(
        "Message", back_populates="conversation", order_by="Message.created_at"
    )
    profile = relationship("UserProfile", back_populates="conversations")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # user | assistant | tool
    content = Column(Text, nullable=False, default="")
    speaker_id = Column(String, nullable=True)
    speaker_confidence = Column(Float, nullable=True)
    tool_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")
