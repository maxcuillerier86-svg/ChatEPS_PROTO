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
1. Ouvrir l’UI, saisir un pseudo, choisir un modèle Ollama (ex: `gpt-oss:20b`, `llama3.1`), puis créer une conversation `co_design`.
2. Uploader des PDFs dans Bibliothèque.
3. Étudiant lance un chat, itère, puis crée artefact.
4. Prof consulte dashboard cohorte et traces.
5. Export possible via endpoints dashboard (extension prévue CSV/JSON).


## 9) Session locale sans authentification
- Bibliothèque PDF locale (UI): upload de PDF, stockage local, sélection des documents puis chat RAG ciblé sur ces PDF.
- Si l’ingestion échoue (modèle d'embeddings indisponible), le document passe en statut `failed` au lieu de casser le serveur.
- Pseudo (pas de mot de passe): l’UI envoie `X-Pseudo` et le backend crée/réutilise automatiquement le profil local associé.
- Les conversations listées sont celles créées par le pseudo actif.
- Sélection de modèle: endpoint `GET /chat/models` + sélection dans l’UI avant envoi.
- Pull de modèle: endpoint `POST /chat/models/pull` (utilisé par le bouton **Pull modèle**), avec support de saisie **OTHER** (ex: `gpt-oss:20b`).

## 10) Dépannage rapide
- Compatibilité embeddings Ollama: le backend tente `/api/embeddings` puis bascule automatiquement vers `/api/embed` si nécessaire.
- Local (hors Docker): `OLLAMA_URL` doit pointer vers `http://localhost:11434`.
- Docker compose: la variable est surchargée vers `http://ollama:11434` automatiquement.
- Compatibilité Windows/passlib: la création de session pseudo ne dépend plus de bcrypt (évite les erreurs `trapped error reading bcrypt version`).
- `WARNING: Invalid HTTP request received.` : souvent causé par un navigateur/extension qui tente HTTPS/WebSocket sur un port HTTP local. Ce warning n’empêche pas le fonctionnement normal de l’API/UI.
- Si vous lancez uniquement `uvicorn app.main:app --reload --port 8000`, l’UI intégrée est disponible sur `http://127.0.0.1:8000`.
- L’ancienne UI Next.js reste disponible sur `http://localhost:3000` si vous lancez aussi le frontend.


## 11) Améliorations RAG (qualité + sécurité + perf)
- Traitement de requête: classification d’intention, expansion sémantique, injection de contexte étudiant (niveau + confiance).
- Retrieval multi-étapes: coarse lexical -> dense vectoriel -> re-ranking, avec filtres de métadonnées (`doc_types`, `tags`).
- Segmentation documentaire: `theory`, `practice`, `reflection`, `artifacts` + stratégie de chunking adaptée.
- Compression de contexte avant génération pour limiter le bruit et préserver les citations utiles.
- Mode `strict_grounding`: si preuves insuffisantes, réponse explicite plutôt qu’hallucination.
- Cache embeddings (TTL/LRU) pour réduire latence et appels Ollama redondants.

Voir `docs/RAG_SYSTEM_UPGRADE.md` pour le pipeline détaillé et les templates de prompt.
