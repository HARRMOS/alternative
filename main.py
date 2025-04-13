from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Text, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Remplace par tes vraies infos de connexion
DATABASE_URL = "mysql+pymysql://root:Harris91270@localhost/VieAlternative"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI()

# ----------------------
# Modèles SQLAlchemy
# ----------------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)

class Mission(Base):
    __tablename__ = "missions"
    id = Column(Integer, primary_key=True)
    life_id = Column(Integer, nullable=False)
    level_number = Column(Integer, nullable=False)
    title = Column(String(100), nullable=False)
    description = Column(Text)
    points = Column(Integer, default=10)

class UserProgress(Base):
    __tablename__ = "user_progress"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    mission_id = Column(Integer, ForeignKey("missions.id"))
    completed = Column(Boolean, default=False)
    completed_at = Column(TIMESTAMP, nullable=True)

# ----------------------
# Pydantic Schemas
# ----------------------
class MissionSchema(BaseModel):
    id: int
    life_id: int
    level_number: int
    title: str
    description: str
    points: int

    class Config:
        orm_mode = True

class MissionComplete(BaseModel):
    user_id: int
    mission_id: int

# ----------------------
# Routes
# ----------------------
@app.get("/missions/{user_id}", response_model=List[MissionSchema])
def get_available_missions(user_id: int):
    db = SessionLocal()
    try:
        completed_ids = db.query(UserProgress.mission_id).filter_by(user_id=user_id, completed=True).all()
        completed_ids = [m[0] for m in completed_ids]
        missions = db.query(Mission).filter(~Mission.id.in_(completed_ids)).all()
        return missions
    finally:
        db.close()

@app.post("/complete_mission")
def complete_mission(data: MissionComplete):
    db = SessionLocal()
    try:
        # Vérifie si déjà complétée
        existing = db.query(UserProgress).filter_by(user_id=data.user_id, mission_id=data.mission_id).first()
        if existing and existing.completed:
            raise HTTPException(status_code=400, detail="Mission déjà complétée")

        if existing:
            existing.completed = True
            existing.completed_at = datetime.utcnow()
        else:
            progress = UserProgress(
                user_id=data.user_id,
                mission_id=data.mission_id,
                completed=True,
                completed_at=datetime.utcnow()
            )
            db.add(progress)

        db.commit()
        return {"message": "Mission complétée avec succès"}
    finally:
        db.close()
