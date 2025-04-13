from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from datetime import datetime

DATABASE_URL = "mysql+pymysql://root:Harris91270@localhost/VieAlternative"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI()

# -----------------------
# Database Models
# -----------------------
class Life(Base):
    __tablename__ = "lives"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(100))

class Mission(Base):
    __tablename__ = "missions"
    id = Column(Integer, primary_key=True)
    life_id = Column(Integer, ForeignKey("lives.id"))
    level_number = Column(Integer)
    title = Column(String(255))
    description = Column(String(500))
    points = Column(Integer)

class UserLifeProgress(Base):
    __tablename__ = "user_life_progress"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    life_id = Column(Integer, ForeignKey("lives.id"))
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)

    user = relationship("User")
    life = relationship("Life")

class UserProgress(Base):
    __tablename__ = "user_progress"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    mission_id = Column(Integer, ForeignKey("missions.id"))
    completed = Column(Integer, default=0)
    completed_at = Column(String(255), nullable=True)
    user_photo_url = Column(String(255), nullable=True)

    user = relationship("User")
    mission = relationship("Mission")

class UserReward(Base):
    __tablename__ = "user_rewards"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    reward_name = Column(String(255))
    rewarded_at = Column(String(255))  # Date de la récompense

    user = relationship("User")

# Assure-toi de créer la table après avoir ajouté ce modèle
Base.metadata.create_all(bind=engine)

# -----------------------
# Utility functions
# -----------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

LEVEL_THRESHOLDS = {
    1: 0,
    2: 50,
    3: 150,
    4: 300,
    5: 500,
}

def get_level_from_xp(xp):
    level = 1
    for lvl, threshold in sorted(LEVEL_THRESHOLDS.items()):
        if xp >= threshold:
            level = lvl
    return level

def get_next_level_threshold(current_level):
    return LEVEL_THRESHOLDS.get(current_level + 1, None)

def grant_rewards(user_id: int, level: int, db: Session):
    # Exemple simple de récompenses basées sur le niveau
    rewards = {
        2: "Récompense: Badge de Boulanger Novice",
        3: "Récompense: Badge de Boulanger Expert",
        4: "Récompense: Badge de Boulanger Pro",
    }

    reward = rewards.get(level)
    if reward:
        # Enregistrer la récompense dans la base de données
        db.add(UserReward(
            user_id=user_id,
            reward_name=reward,
            rewarded_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        db.commit()
        return reward
    return None

# -----------------------
# Routes
# -----------------------

@app.get("/users/{user_id}/available_missions")
def get_available_missions(user_id: int, db: Session = Depends(get_db)):
    # Récupère les progrès de l'utilisateur
    progress = db.query(UserLifeProgress).filter_by(user_id=user_id).first()
    if not progress:
        raise HTTPException(status_code=404, detail="Progress not found")

    # Récupère les missions disponibles en fonction du niveau de l'utilisateur
    level = get_level_from_xp(progress.xp)
    
    # Récupérer les missions en fonction du niveau
    missions = db.query(Mission).filter(Mission.level_number <= level).all()
    
    if not missions:
        raise HTTPException(status_code=404, detail="No missions available for your level")

    # Retourner les missions
    return {"user_id": user_id, "level": level, "missions": [mission.title for mission in missions]}


@app.get("/users/{user_id}/profile")
def get_user_profile(user_id: int, db: Session = Depends(get_db)):
    progress = db.query(UserLifeProgress).filter_by(user_id=user_id).first()
    if not progress:
        raise HTTPException(status_code=404, detail="Progress not found")

    current_level = get_level_from_xp(progress.xp)
    next_threshold = get_next_level_threshold(current_level)

    if next_threshold:
        progress_percent = int((progress.xp - LEVEL_THRESHOLDS[current_level]) / (next_threshold - LEVEL_THRESHOLDS[current_level]) * 100)
    else:
        progress_percent = 100

    return {
        "user_id": user_id,
        "life_id": progress.life_id,
        "xp": progress.xp,
        "level_number": current_level,
        "progress_to_next_level": f"{progress_percent}%"
    }

@app.post("/users/{user_id}/complete_mission/{mission_id}")
def complete_mission(user_id: int, mission_id: int, user_photo_url: str = None, db: Session = Depends(get_db)):
    # Vérifie si la mission existe
    mission = db.query(Mission).filter_by(id=mission_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")

    # Vérifie si le user a déjà complété cette mission
    already_done = db.query(UserProgress).filter_by(user_id=user_id, mission_id=mission_id).first()
    if already_done:
        raise HTTPException(status_code=400, detail="Mission already completed")

    # Récupère ou crée le progrès utilisateur
    progress = db.query(UserLifeProgress).filter_by(user_id=user_id, life_id=mission.life_id).first()
    if not progress:
        progress = UserLifeProgress(user_id=user_id, life_id=mission.life_id, xp=0, level=1)
        db.add(progress)
        db.commit()
        db.refresh(progress)

    # Ajoute les points de la mission
    progress.xp += mission.points
    progress.level = get_level_from_xp(progress.xp)

    # Vérifie si l'utilisateur a monté de niveau
    reward = grant_rewards(user_id, progress.level, db)

    # Enregistre la progression de la mission
    user_progress = UserProgress(
        user_id=user_id,
        mission_id=mission_id,
        completed=1,
        completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        user_photo_url=user_photo_url
    )
    db.add(user_progress)
    db.commit()

    return {
        "message": "Mission completed! XP updated.",
        "new_xp": progress.xp,
        "new_level": progress.level,
        "reward": reward if reward else "No new reward"
    }


@app.get("/users/{user_id}/rewards")
def get_user_rewards(user_id: int, db: Session = Depends(get_db)):
    rewards = db.query(UserReward).filter_by(user_id=user_id).all()
    return [{"reward_name": reward.reward_name, "rewarded_at": reward.rewarded_at} for reward in rewards]