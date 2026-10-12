# Puls-Events — POC RAG (événements culturels à Paris)

Assistant de recommandation d’événements culturels pour **Puls-Events**.  
Preuve de concept (POC) : **RAG** (Retrieval-Augmented Generation) avec **LangChain**, **Mistral** et **FAISS**, alimenté par **OpenAgenda**, périmètre **Paris**, événements de **moins d’un an** (historique 12 mois + à venir).

Les livrables applicatifs sont en **français**. L’interface de démonstration aussi.

The original course brief (Jeremy’s email, expected deliverables, guided steps) is in **[`MISSION.md`](./MISSION.md)**.

---

## 1. Ce qui tourne en local vs ce qui est en ligne

| Composant | Où ça s’exécute |
| --- | --- |
| Python, LangChain, FAISS (`faiss-cpu`), tests | **Machine locale** |
| Index vectoriel | Fichiers dans `vector_store/` |
| API OpenAgenda | Internet (collecte des événements) |
| API Mistral (embeddings `mistral-embed` + chat `ministral-8b-latest`) | Internet (console.mistral.ai) |

Pas de GPU, pas de cloud (AWS/GCP), pas de base vectorielle hébergée.

---

## 2. Prérequis

- Python **3.11+** (testé avec 3.12)
- Compte [Mistral](https://console.mistral.ai) + clé API
- Compte [OpenAgenda](https://openagenda.com) + clé publique de lecture

Copiez `.env.example` vers `.env` (déjà fait sur cette machine) :

```
MISTRAL_API_KEY=...
OPENAGENDA_API_KEY=...
CITY=Paris
MAX_EVENTS=350
```

Ne commitez **jamais** le fichier `.env`.

---

## 3. Installation

Depuis ce dossier `project` :

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python check_setup.py
```

`check_setup.py` doit afficher `Environnement OK` et confirmer les imports LangChain / FAISS / Mistral.

---

## 4. Reconstruire la base vectorielle

Le brief demande de pouvoir **reconstruire l’index à la demande** (prétraitement + vectorisation) :

```bash
python rebuild_index.py
```

Options utiles :

```bash
python rebuild_index.py --max-events 200
python rebuild_index.py --skip-fetch          # réutilise data/raw/
python rebuild_index.py --skip-index          # s’arrête après le CSV/JSON nettoyé
```

Pipeline :

1. Collecte OpenAgenda (Paris)
2. Filtre ville + dates < 1 an
3. Structuration JSON (`data/processed/events.json`)
4. Découpage (chunks) LangChain
5. Embeddings Mistral → index **FAISS** (`vector_store/faiss_paris/`)
6. Génération du jeu Q/R annoté (`data/evaluation/annotated_qa.json`)

---

## 5. Démo live (chatbot)

```bash
python ask.py "Propose-moi un concert à Paris"
```

Chaque question est indépendante : **pas d’historique de conversation** dans le POC, conformément au brief.

---

## 6. Tests unitaires

Le fichier demandé par le brief :

```bash
pytest tests/test_events_freshness.py tests/test_imports.py
```

Ces tests vérifient :

- que les filtres rejettent Lyon / les dates de plus d’un an ;
- que le jeu traité (`events.json`) ne contient que des événements **Paris** et **< 12 mois** ;
- que les métadonnées de l’index FAISS respectent le même périmètre ;
- que LangChain, FAISS et Mistral s’importent.

---

## 7. Jeu de test annoté et évaluation

```bash
python evaluate.py           # retrieval (FAISS vs annotations)
python evaluate.py --llm     # + réponses générées (quota Mistral)
```

Les paires question / réponse annotée sont dans `data/evaluation/annotated_qa.json`.  
Une réponse du système est jugée correcte si elle **contient les mêmes informations clés** que l’annotation (titre, lieu).

---

## 8. Livrables documentaires

Générés dans `docs/` :

```bash
python docs/generate_deliverables.py
```

- `docs/rapport.md` — source du rapport
- `docs/rapport.docx` — rapport technique Word (5–10 pages)
- `docs/rapport.pdf` — version PDF
- `docs/presentation.pptx` — 12 slides

---

## 9. Architecture

```
OpenAgenda (Paris)
        │  ingest
        ▼
  événements JSON  →  filtres (ville + 12 mois)  →  chunks LangChain
                                                          │
                                                          ▼
                                              embeddings Mistral
                                                          │
                                                          ▼
                                                    index FAISS
                                                          │
Question utilisateur  →  embedding  →  top-k extraits  →  Mistral (génération)
                                                          │
                                                          ▼
                                              recommandation + sources
```

---

## 10. Structure du dépôt

```
project/
  ask.py                  # démo en ligne de commande
  rebuild_index.py        # reconstruction de l'index
  evaluate.py             # qualité vs jeu annoté
  check_setup.py
  requirements.txt
  src/pulsevents/         # code métier
  tests/                  # tests unitaires
  data/                   # brut / traité / évaluation
  vector_store/           # FAISS
  docs/                   # rapport + slides
```

---

## 11. Choix techniques (résumé)

| Sujet | Choix | Pourquoi |
| --- | --- | --- |
| Orchestration | LangChain | Imposé + chaînes retriever → prompt → LLM |
| Vecteurs | FAISS `IndexFlatIP` (via LangChain) | Local, CPU, adapté au volume du POC |
| Embeddings | `mistral-embed` | Cohérent avec la plateforme Mistral du brief |
| LLM | `ministral-8b-latest` | Autorisé par la clé Mistral du POC, français correct, faible latence |
| Données | OpenAgenda | Source publique demandée |
| Périmètre | Paris intramuros | Volume suffisant, filtres testables |

Recommandations pour une version finale : reranking, filtres métadonnées (dates / arrondissement) dans FAISS, modèle plus grand si le budget le permet, observabilité des hallucinations.
