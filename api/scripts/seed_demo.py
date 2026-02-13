from pathlib import Path

from pypdf import PdfWriter

from app.core.database import Base, SessionLocal, engine
from app.core.security import get_password_hash
from app.models.entities import Course, User

Base.metadata.create_all(bind=engine)
db = SessionLocal()

if not db.query(Course).first():
    db.add(Course(name="Didactique EPS – Hiver 2026", cohort="Hiver2026-A"))

users = [
    ("admin@cope.local", "Admin Co-PE", "admin"),
    ("prof@cope.local", "Prof EPS", "teacher"),
    ("etudiant1@cope.local", "Étudiant 1", "student"),
    ("etudiant2@cope.local", "Étudiant 2", "student"),
]
for email, name, role in users:
    if not db.query(User).filter(User.email == email).first():
        db.add(User(email=email, full_name=name, role=role, hashed_password=get_password_hash("password123")))
db.commit()

pdf_dir = Path("data/pdfs")
pdf_dir.mkdir(parents=True, exist_ok=True)
for name in ["guide_didactique.pdf", "evaluation_eps.pdf"]:
    path = pdf_dir / name
    if not path.exists():
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        with path.open("wb") as f:
            writer.write(f)

print("Demo seed completed")
