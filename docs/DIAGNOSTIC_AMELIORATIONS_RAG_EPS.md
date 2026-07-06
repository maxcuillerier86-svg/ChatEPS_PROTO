# Diagnostic fonctionnel et UI/UX — chat-EPS (RAG pour éducateurs en ÉPS)

> Analyse basée sur le code du dépôt au 2026-07-06 (branche `main`, commit `b3d357b`) :
> API FastAPI (`api/app`), UI intégrée (`api/app/static/index.html`), pipeline RAG
> (`api/app/services/rag.py`), modèles de données (`api/app/models/entities.py`).

---

## 1. État des lieux (ce que fait l'outil aujourd'hui)

| Domaine | Constat (code) |
|---|---|
| **Ingestion** | PDF découpés en tranches fixes de 900 caractères (chevauchement 150), sans respect des paragraphes ni des titres de section (`rag.py:14`). Métadonnées indexées : `doc_id`, `title`, `page` seulement. Le champ `tags` existe en base (`entities.py:37`) mais n'est **ni exposé dans l'UI, ni indexé dans Qdrant**. |
| **Retrieval** | Vectoriel (Qdrant, cosine) avec repli lexical local si embeddings indisponibles (`rag.py:119`). Filtrage uniquement par documents cochés. Aucun filtre niveau scolaire / matériel / durée / compétence. Pas de fusion hybride : le lexical n'est utilisé qu'en secours, jamais combiné. |
| **Génération** | 5 postures pédagogiques (co-conception, exploration, critique, justification, éval. réflexive) via prompts système (`chat.py:17`). **Toute** réponse se termine par une auto-évaluation 1-5, quel que soit le mode (`chat.py:211`) — pertinent pour la recherche, pas pour un enseignant pressé. Pas de gabarit structuré de séance. |
| **Citations** | Titre + page + extrait 280 caractères, repliées dans un `<details>`. Pas de lien vers le PDF, pas de distinction du type de source. |
| **UI** | 3 colonnes desktop, onglets mobiles, thème sombre, suggestions de départ, dropzone PDF. Mais l'utilisateur doit : choisir un **pseudo**, choisir un **modèle Ollama**, éventuellement le *puller*, cocher les PDF, activer/désactiver le RAG — beaucoup de décisions techniques avant la première question. |
| **Déjà en base, non exploité** | `Course` (groupe-classe), `Artifact`/`ArtifactVersion` (fiches versionnées), `tags` sur les PDF. Trois briques existantes qui couvrent une bonne partie des « fonctionnalités manquantes ». |

---

## 2. Diagnostic fonctionnel

### 2.1 Pertinence du retrieval

**Problème central : le contexte d'enseignement n'existe nulle part.** La requête part
telle quelle vers l'embedding ; « échauffement » retourne les mêmes chunks pour un
groupe de 1re année dans un demi-gymnase et pour du secondaire 5 en piste extérieure.

Recommandations, par ordre de coût croissant :

1. **Profil de séance côté client** (niveau/cycle, durée, matériel, taille du groupe,
   contraintes particulières). Injecté (a) dans le prompt système, (b) concaténé à la
   requête d'embedding. Zéro changement d'index : gain immédiat de pertinence pour
   un effort de quelques heures.
2. **Métadonnées à l'upload** : type de source (`programme_officiel` /
   `banque_exercices` / `contribution_collegue`), cycle(s) visé(s), tags libres.
   Le champ `tags` existe déjà (`PdfDocument.tags`) ; il faut l'exposer dans le
   formulaire d'upload et le copier dans le payload Qdrant.
3. **Filtrage/pondération par payload** : filtre Qdrant `must` sur le cycle quand il
   est connu ; sur-pondération (boost de score) des chunks `programme_officiel`
   quand la question porte sur l'évaluation ou les compétences.
4. **Fusion hybride** : combiner les scores lexicaux (déjà calculés dans
   `_lexical_score`) et vectoriels par Reciprocal Rank Fusion, au lieu du simple
   fallback. Important pour le vocabulaire ÉPS très spécifique (« ballon-chasseur »,
   « kin-ball ») que les embeddings généralistes couvrent mal.
5. **Chunking sensible à la structure** : découper aux frontières de paragraphes et
   préfixer chaque chunk du titre de section détecté. Améliore à la fois le retrieval
   et la lisibilité des citations.

### 2.2 Qualité des réponses générées

**Problème central : la sortie est un texte libre de chatbot, pas un document de
travail.** Un enseignant debout entre deux groupes a besoin d'une fiche scannable.

1. **Gabarit « fiche de séance »** imposé par le prompt du mode co-conception :
   *Objectif · Matériel · Durée · Déroulé (échauffement / corps / retour au calme,
   avec minutage) · Variante + (plus difficile) · Variante − (plus simple) ·
   Points de sécurité · Critères d'observation*. C'est un changement de prompt, pas
   de code.
2. **Réponses courtes d'abord** : demander une fiche condensée (~15 lignes), avec
   la possibilité de demander le détail. Supprimer l'auto-évaluation 1-5
   systématique — la conserver uniquement en mode `evaluation_reflexive` (elle y est
   déjà définie dans le prompt du mode ; la ligne `chat.py:211` la duplique partout).
3. **Boutons d'adaptation en un geste** sous chaque réponse : « Moins d'espace »,
   « Sans matériel », « Plus simple », « Plus difficile », « Élève à besoins
   particuliers ». Techniquement triviaux (prompts pré-remplis renvoyés dans la même
   conversation), très forte valeur d'usage — c'est l'« adaptation en temps réel »
   demandée, à portée d'un RAG.
4. **Signal d'ancrage** : indiquer en tête de réponse si elle s'appuie sur des
   sources (« 📎 basé sur 3 sources ») ou non (« ⚠ réponse générale, non ancrée sur
   vos documents »). L'information existe déjà dans `citations`.

### 2.3 Fonctionnalités manquantes — et comment les obtenir à moindre coût

| Fonctionnalité manquante | Brique existante à réutiliser | Effort |
|---|---|---|
| **Favoris / collections de séances** | `Artifact` + `ArtifactVersion` déjà en base : un bouton « 💾 Enregistrer comme fiche » sur une réponse crée un artefact ; un onglet « Mes fiches » les liste | Moyen |
| **Historique par groupe-classe** | `Course` + `conversation.course_id` déjà en base : sélecteur de groupe à la création de conversation, filtre dans la liste | Moyen |
| **Mode hors-ligne gymnase** | Le serveur est déjà local/LAN. Ajouter un manifest PWA + cache des fiches favorites pour **consultation** hors réseau (la génération, elle, exige le serveur — limite à assumer) | Moyen |
| **Suggestions proactives** | Suggestions d'accueil déjà en place (`renderEmptyChat`) : les rendre contextuelles (dernier groupe consulté, saison, fiches récentes) | Faible → Moyen |
| **Export / impression** | Fiche structurée en Markdown → gabarit d'impression CSS (`@media print`) ou export PDF côté serveur | Faible (impression) |

---

## 3. Amélioration UI/UX

### 3.1 Principe directeur : réduire le coût d'entrée

Le parcours actuel avant la première réponse : pseudo → modèle Ollama → (pull ?) →
démarrer la session → uploader/cocher des PDF → vérifier le toggle RAG → écrire.
Pour un public non technophile, chaque étape est un point d'abandon.

- **Choisir un modèle par défaut automatiquement** (premier modèle disponible via
  `/chat/models`) ; reléguer sélection et pull dans « Options avancées » (le repli
  existe déjà pour le pull). Le mot « Ollama » ne devrait jamais apparaître dans
  l'écran principal.
- **Supprimer l'étape « Démarrer la session »** : demander le prénom au premier
  envoi (une seule question, une seule fois), le mémoriser en `localStorage` comme
  aujourd'hui.
- **Cocher par défaut tous les documents « prêts »** et remplacer le couple
  toggle RAG + cases à cocher par un seul état visible : « Répond à partir de
  N documents — modifier ».
- **Mobile debout = cibles larges** : boutons ≥ 44 px, suggestions et boutons
  d'adaptation en gros « chips », taille de police des réponses ≥ 16 px.

### 3.2 Architecture de l'information proposée

```
┌────────────────────────────────────────────┐
│ [Nouvelle demande] [Mes fiches] [Documents]│  ← 3 sections, pas 3 colonnes
└────────────────────────────────────────────┘
```

- **Nouvelle demande** : barre de contexte (chips niveau / durée / matériel) +
  champ de question + suggestions.
- **Mes fiches** : favoris et historique, filtrables par groupe-classe.
- **Documents** : bibliothèque avec badges de type de source et statut d'ingestion.

Le mode « posture pédagogique » (co-conception, critique…) est pertinent pour le
volet recherche/formation, mais pour l'enseignant en exercice il devrait se réduire
à deux intentions : **« Créer une séance »** et **« Poser une question »** — les
autres postures restant accessibles en avancé.

### 3.3 Citation des sources sans surcharge

- **Badge compact sous la réponse** : `📗 Programme officiel · p. 34` /
  `📘 Banque d'exercices` / `👤 Collègue (Nom)` — couleur + icône par type,
  extrait complet seulement au toucher (le `<details>` actuel est le bon réflexe,
  il manque le typage et le lien).
- **Lien d'ouverture du PDF à la page** : servir `storage/pdfs/` en statique et
  pointer `fichier.pdf#page=34`.
- **Règle d'affichage** : max 3 badges visibles, « +2 sources » pour le reste.

### 3.4 Wireframes (3 écrans clés)

**Écran A — Nouvelle demande (mobile)**

```
┌──────────────────────────────┐
│ chat-EPS            [👤 Max] │
├──────────────────────────────┤
│ Contexte de la séance        │
│ [3e cycle ▾][55 min ▾]       │
│ [Gymnase simple ▾][28 él. ▾] │
├──────────────────────────────┤
│ ┌──────────────────────────┐ │
│ │ Que voulez-vous préparer?│ │
│ └──────────────────────[➤]┘ │
│                              │
│ Suggestions pour vous :      │
│ [🏐 Séance volley débutants] │
│ [🏃 Relais sans matériel   ] │
│ [♿ Adapter pour Léa (TSA)  ] │
│                              │
│ 📎 Répond à partir de 4 docs │
│    (modifier)                │
└──────────────────────────────┘
```
Les chips de contexte sont persistantes (mémorisées par groupe-classe) : on les
règle une fois par groupe, pas à chaque question.

**Écran B — Réponse « fiche de séance »**

```
┌──────────────────────────────┐
│ ← Séance volley — 3e cycle   │
├──────────────────────────────┤
│ 🎯 Objectif : passes hautes  │
│ 🧰 Matériel : 8 ballons, 2   │
│    filets · ⏱ 55 min         │
│ ── Déroulé ────────────────  │
│ 10' Échauffement : …         │
│ 30' Cœur de séance : …       │
│ 10' Retour au calme : …      │
│ ── Sécurité ⚠ ─────────────  │
│ • Espacement des terrains …  │
├──────────────────────────────┤
│ [− Plus simple][+ Difficile] │
│ [Sans matériel][½ gymnase ]  │
├──────────────────────────────┤
│ Sources: 📗 Programme p.34   │
│ 📘 Banque exercices · +1     │
├──────────────────────────────┤
│ [💾 Enregistrer] [🖨 Imprimer]│
└──────────────────────────────┘
```

**Écran C — Documents (bibliothèque typée)**

```
┌──────────────────────────────┐
│ Documents          [+ Ajouter]│
│ Filtres: [Tous][📗][📘][👤]  │
├──────────────────────────────┤
│ 📗 PFEQ — ÉPS primaire       │
│    Programme officiel · prêt │
│ 📘 Banque jeux coopératifs   │
│    2e-3e cycle · prêt        │
│ 👤 Évaluations de Marc       │
│    Collègue · indexation…    │
└──────────────────────────────┘
```
À l'ajout : 3 questions seulement — titre (pré-rempli), type de source (3 gros
boutons radio), cycle(s) (chips multi-sélection).

---

## 4. Priorisation

### Horizon 1 — Rapide / fort impact (jours)

| # | Recommandation | Problème résolu | Effort |
|---|---|---|---|
| 1 | Gabarit « fiche de séance » via prompt de mode | Réponses non actionnables | XS |
| 2 | Auto-évaluation 1-5 limitée au mode réflexif | Réponses inutilement longues | XS |
| 3 | Modèle par défaut automatique, jargon Ollama masqué | Barrière technique à l'entrée | S |
| 4 | Documents « prêts » cochés par défaut, état RAG unifié | Réponses vides de sources par oubli de cochage | S |
| 5 | Boutons d'adaptation (plus simple / sans matériel / etc.) | Pas d'adaptation en un geste | S |
| 6 | Signal « ancré sur N sources / non ancré » en tête de réponse | Confiance et vérifiabilité | XS |
| 7 | Profil de séance (chips contexte) injecté dans prompt + requête | Retrieval et réponses hors contexte | S–M |

### Horizon 2 — Moyen terme (semaines)

| # | Recommandation | Problème résolu | Effort |
|---|---|---|---|
| 8 | Métadonnées d'upload (type de source, cycle) + payload Qdrant | Sources indifférenciées | M |
| 9 | Filtres/pondération de retrieval par métadonnées | Résultats hors niveau/contexte | M |
| 10 | Fusion hybride lexical+vectoriel (RRF) | Vocabulaire ÉPS mal couvert par embeddings | M |
| 11 | « Mes fiches » : favoris via `Artifact` existant | Séances perdues dans l'historique de chat | M |
| 12 | Groupes-classes via `Course` existant + historique filtré | Pas de suivi par groupe | M |
| 13 | Impression / gabarit print CSS des fiches | Usage papier au gymnase | S |
| 14 | Citations typées + lien PDF ancré à la page | Provenance opaque | M |
| 15 | Chunking par paragraphe avec titres de section | Chunks tronqués, citations illisibles | M |

### Horizon 3 — Vision long terme (trimestres)

| # | Recommandation | Problème résolu |
|---|---|---|
| 16 | Refonte « banque de fiches d'abord » : la recherche retourne des fiches structurées ; le chat devient l'outil d'adaptation | Le chat comme unique porte d'entrée ne correspond pas à l'usage pressé |
| 17 | PWA + cache hors-ligne des fiches favorites (consultation seule) | Gymnase sans Wi-Fi fiable |
| 18 | Suggestions proactives (saison, planification annuelle, dernier groupe) | Page d'accueil générique |
| 19 | Partage entre collègues avec validation (contributions typées 👤) | Savoir local non capitalisé |
| 20 | Référentiel PFEQ structuré (compétences/critères en données, pas en PDF) | Alignement programme approximatif |

---

## 5. Questions ouvertes / hypothèses à valider auprès d'enseignants d'ÉPS

1. **Support d'usage réel au gymnase** : téléphone dans la poche, tablette sur un
   chariot, ou feuille imprimée préparée la veille ? (Détermine la priorité entre
   mode mobile et impression — nos hypothèses H1 « mobile debout » et H13
   « impression » sont concurrentes.)
2. **Moment de préparation** : les séances se préparent-elles surtout à l'avance
   (bureau, soir) ou s'ajustent-elles en direct ? (Arbitre entre fiche riche et
   boutons d'adaptation temps réel.)
3. Le **gabarit de fiche** proposé (objectif/matériel/déroulé/variantes/sécurité)
   correspond-il à leurs formats existants (planifications exigées par la
   direction, canevas universitaires) ?
4. **Confiance dans les sources** : une réponse « non ancrée » (sans PDF) est-elle
   acceptable, ou faut-il la bloquer/dégrader visuellement ?
5. Les enseignants veulent-ils **citer le programme officiel** dans leurs
   documents remis (auquel cas la page exacte est cruciale) ou est-ce surtout une
   réassurance ?
6. **Granularité du contexte** : niveau + matériel + durée suffisent-ils, ou le
   facteur dominant est-il ailleurs (météo pour l'extérieur, composition du
   groupe, élèves HDAA) ?
7. **Partage entre collègues** : y a-t-il une culture d'échange de documents dans
   les établissements cibles, ou la bibliothèque restera-t-elle individuelle ?
   (Conditionne l'horizon 3.)
8. **Vitesse de génération locale** : quel temps d'attente est acceptable ?
   (Un modèle 20B local peut mettre >30 s ; cela peut disqualifier l'usage debout
   et re-prioriser les fiches pré-générées.)
9. Les **5 postures pédagogiques** ont-elles un sens pour un enseignant en
   exercice, ou sont-elles un artefact du contexte recherche/formation initiale
   (étudiants UQAM) ? Faut-il deux profils de produit distincts ?
10. **Un seul pseudo sans mot de passe** est-il acceptable dans un établissement
    (postes partagés) une fois que des documents personnels y sont attachés ?

---

## Annexe — Correspondances code pour l'implémentation

- Gabarit de fiche & auto-évaluation : `api/app/routers/chat.py:17` (`MODE_SYSTEM`) et `:211` (suffixe systématique).
- Profil de séance : nouveau champ dans `MessageIn` (`api/app/schemas/chat.py:11`) + concaténation dans `stream_reply`.
- Métadonnées upload : `api/app/routers/library.py:22` (le champ `tags` est déjà accepté en `Form`) ; payload Qdrant dans `api/app/services/rag.py:100`.
- Fusion hybride : `retrieve()` dans `api/app/services/rag.py:119` (les deux voies existent, il manque la fusion).
- Favoris : réutiliser `Artifact` (`api/app/models/entities.py:66`) et le routeur `api/app/routers/artifacts.py`.
- Groupes-classes : `Course` (`api/app/models/entities.py:24`), `conversation.course_id` déjà persisté.
- Sélection par défaut des PDF & état RAG : `api/app/static/index.html` (`refreshPdfs`, `updateRagHint`).
