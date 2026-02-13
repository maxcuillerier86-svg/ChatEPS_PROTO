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
- UI FastAPI intégrée: http://localhost:8000
- Web Next.js (optionnel): http://localhost:3000
- API docs: http://localhost:8000/docs

## 4) Lancement dev sans Docker
### Mac/Linux
```bash
cd api && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Optionnel mais recommandé hors Docker:
# export OLLAMA_URL=http://localhost:11434
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
# Optionnel mais recommandé hors Docker:
$env:OLLAMA_URL="http://localhost:11434"
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
1. Ouvrir l’UI, saisir un pseudo, choisir un modèle Ollama (ex: `gpt-oss:20b`, `llama3.1`), puis créer une conversation `co_design`.
2. Uploader des PDFs dans Bibliothèque.
3. Étudiant lance un chat, itère, puis crée artefact.
4. Prof consulte dashboard cohorte et traces.
5. Export possible via endpoints dashboard (extension prévue CSV/JSON).


## 9) Session locale sans authentification
- Pseudo (pas de mot de passe): l’UI envoie `X-Pseudo` et le backend crée/réutilise automatiquement le profil local associé.
- Les conversations listées sont celles créées par le pseudo actif.
- Sélection de modèle: endpoint `GET /chat/models` + sélection dans l’UI avant envoi.
- Pull de modèle: endpoint `POST /chat/models/pull` (utilisé par le bouton **Pull modèle**), avec support de saisie **OTHER** (ex: `gpt-oss:20b`).

## 10) Dépannage rapide
- `getaddrinfo failed` / hôte `ollama`: vous lancez probablement hors Docker avec une URL Docker. Fixez `OLLAMA_URL=http://localhost:11434` dans l’environnement ou `.env` du dossier `api`.
- Compatibilité Windows/passlib: la création de session pseudo ne dépend plus de bcrypt (évite les erreurs `trapped error reading bcrypt version`).
- `WARNING: Invalid HTTP request received.` : souvent causé par un navigateur/extension qui tente HTTPS/WebSocket sur un port HTTP local. Ce warning n’empêche pas le fonctionnement normal de l’API/UI.
- Si vous lancez uniquement `uvicorn app.main:app --reload --port 8000`, l’UI intégrée est disponible sur `http://127.0.0.1:8000`.
- L’ancienne UI Next.js reste disponible sur `http://localhost:3000` si vous lancez aussi le frontend.
