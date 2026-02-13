import re

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token, get_password_hash
from app.models.entities import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _pseudo_to_email(pseudo: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", pseudo.lower()).strip("-")
    slug = slug or "participant"
    return f"{slug}@cope.local"


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    email = decode_token(token)
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable")
    return user


def get_actor_user(
    x_pseudo: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not x_pseudo or not x_pseudo.strip():
        raise HTTPException(status_code=400, detail="Pseudo requis via en-tête X-Pseudo")
    pseudo = x_pseudo.strip()[:80]
    email = _pseudo_to_email(pseudo)
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            full_name=pseudo,
            role="student",
            hashed_password=get_password_hash("pseudo-only-session"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def require_roles(*roles: str):
    def _checker(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Accès refusé")
        return user

    return _checker
