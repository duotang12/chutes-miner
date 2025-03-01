"""
Server (kubernetes node) tracking ORM.
"""

from pydantic import BaseModel, Field
from typing import Literal
from sqlalchemy import Column, String, DateTime, Integer, BigInteger, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from api.database import Base


class ServerArgs(BaseModel):
    name: str
    validator: str
    hourly_cost: float
    gpu_short_ref: Literal[
        "3090",
        "4090",
        "a4000",
        "a5000",
        "a6000",
        "a6000_ada",
        "l4",
        "t4",
        "a30",
        "a40",
        "l40",
        "l40s",
        "a100_40gb",
        "a100",
        "a100_sxm",
        "h100",
        "h100_sxm",
        "h200",
    ] = Field(description="GPU model identifier")


class Server(Base):
    __tablename__ = "servers"

    server_id = Column(String, primary_key=True)
    validator = Column(String, nullable=False)
    name = Column(String, unique=True, nullable=False)
    ip_address = Column(String)
    verification_port = Column(Integer)
    status = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    labels = Column(JSONB, nullable=False)
    seed = Column(BigInteger)
    gpu_count = Column(Integer, nullable=False)
    cpu_per_gpu = Column(Integer, nullable=False, default=1)
    memory_per_gpu = Column(Integer, nullable=False, default=1)
    hourly_cost = Column(Float, nullable=False)

    gpus = relationship("GPU", back_populates="server", lazy="joined", cascade="all, delete-orphan")
    deployments = relationship(
        "Deployment", back_populates="server", lazy="joined", cascade="all, delete-orphan"
    )
