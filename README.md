# Co-PE (Co-creation for Physical Education)

Plateforme locale (offline/LAN) de co-création IA-Humain pour EPS, avec Ollama + RAG PDF + artefacts versionnés + traces de progression novice→expert.

## 1) Plan d'architecture

```text
[Next.js Web FR UI]
  ├─ Chat Co-création (stream SSE)
  ├─ Bibliothèque PDF (upload + statut ingestion)
  ├─ Atelier d’artefacts (versions + workflow)
  └─ Dashboard progression + consentement
        |
        v
[FastAPI API]
  ├─ Auth JWT + bcrypt
  ├─ Conversations/messages/modes
  ├─ RAG orchestration
  ├─ Artefacts + historique
  ├─ Traces pédagogiques + exports
  └─ Santé système
        |
   ┌────┴──────────┐
   v               v
[SQLite]       [Qdrant]
(users,cours,  (chunks + embeddings)
conversations,
artefacts,traces)
        |
        v
[Ollama local API]
  ├─ /api/chat (stream)
  └─ /api/embeddings
```

## 2) Modèle de données (résumé)
- `users`: rôles `student|teacher|admin`, hash mot de passe.
- `courses`: cours/cohorte.
- `pdf_documents`: métadonnées + statut ingestion.
- `conversations` / `messages`: chat multi-tours/modes + citations.
- `artefacts` / `artefact_versions`: co-création et historique.
- `trace_events`: indicateurs (itérations, citations, autonomie, etc.).
- `consents`: consentement éthique recherche.

## 3) Lancement rapide (Docker)
```bash
cp .env.example .env
docker compose up --build
```
- Web: http://localhost:3000
- API docs: http://localhost:8000/docs

## 4) Lancement dev sans Docker
### Mac/Linux
```bash
cd api && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
```bash
cd web && npm install && npm run dev
```
### Windows (PowerShell)
```powershell
cd api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
```powershell
cd web
npm install
npm run dev
```

## 5) Données de démo
```bash
cd api
python scripts/seed_demo.py
```
Comptes (mot de passe `password123`) :
- admin@cope.local
- prof@cope.local
- etudiant1@cope.local
- etudiant2@cope.local

PDF de démo: `guide_didactique.pdf`, `evaluation_eps.pdf` dans `api/data/pdfs`.

## 6) Tests minimaux
```bash
cd api
pytest
```
> Si vous voyez `ModuleNotFoundError: app.main` sous Windows, exécutez bien `pytest` depuis `api/` (pas la racine). Le projet inclut `api/pytest.ini` + `api/tests/conftest.py` pour forcer le `PYTHONPATH` local.

## 7) Sécurité et confidentialité
- Aucun appel cloud imposé; services locaux uniquement.
- JWT + bcrypt.
- Validation extension PDF.
- Journalisation d’événements (traces pédagogiques).
- Séparation logique cours/cohorte via `course_id` (à renforcer en ACL fines).

## 8) Scénario démo recommandé
1. Login professeur, créer conversation mode `co_design`.
2. Uploader des PDFs dans Bibliothèque.
3. Étudiant lance un chat, itère, puis crée artefact.
4. Prof consulte dashboard cohorte et traces.
5. Export possible via endpoints dashboard (extension prévue CSV/JSON).
