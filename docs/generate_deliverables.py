"""Génère le rapport technique (MD, Word, PDF) et la présentation PowerPoint."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt
from fpdf import FPDF
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt as PptPt

from pulsevents.config import (
    CHAT_MODEL,
    CITY,
    DOCS_DIR,
    EMBEDDING_MODEL,
    EVAL_RESULTS_PATH,
    PROCESSED_EVENTS_PATH,
    VECTOR_STORE_DIR,
)


def load_stats() -> dict:
    stats = {
        "city": CITY,
        "n_events": "n/d",
        "n_chunks": "n/d",
        "accuracy": "n/d",
        "coverage": "n/d",
        "n_questions": "n/d",
        "date": datetime.now().strftime("%d/%m/%Y"),
        "venues": [],
        "keywords": [],
    }
    if PROCESSED_EVENTS_PATH.exists():
        events = json.loads(PROCESSED_EVENTS_PATH.read_text(encoding="utf-8"))
        stats["n_events"] = len(events)
        venues = [e.get("venue") for e in events if e.get("venue")]
        kws: list[str] = []
        for e in events:
            kws.extend(e.get("keywords") or [])
        stats["venues"] = sorted(set(venues))[:12]
        stats["keywords"] = sorted(set(kws))[:15]
    meta_path = VECTOR_STORE_DIR / "build_meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        stats["n_chunks"] = meta.get("n_chunks", stats["n_chunks"])
        stats["n_events"] = meta.get("n_events", stats["n_events"])
    if EVAL_RESULTS_PATH.exists():
        ev = json.loads(EVAL_RESULTS_PATH.read_text(encoding="utf-8"))
        stats["accuracy"] = ev.get("accuracy", "n/d")
        stats["coverage"] = ev.get("mean_coverage", "n/d")
        stats["n_questions"] = ev.get("n_questions", "n/d")
    return stats


def report_paragraphs(stats: dict) -> list[tuple[str, str]]:
    """Liste (style, texte) : h1, h2, p, bullet."""
    acc = stats["accuracy"]
    cov = stats["coverage"]
    nq = stats["n_questions"]
    ne = stats["n_events"]
    nc = stats["n_chunks"]
    venues = ", ".join(stats["venues"][:8]) or "en cours de collecte"
    kws = ", ".join(stats["keywords"][:10]) or "concert, exposition, théâtre, festival"

    return [
        ("h1", "Rapport technique — POC RAG Puls-Events"),
        ("p", f"Assistant de recommandation d’événements culturels · Périmètre {stats['city']} · {stats['date']}"),
        ("h2", "1. Contexte et objectif"),
        (
            "p",
            "Puls-Events exploite une plateforme de découverte d’événements culturels en temps réel, "
            "alimentée notamment par OpenAgenda. L’entreprise souhaite tester un chatbot capable de "
            "fournir des recommandations personnalisées, augmentées par des réponses précises tirées "
            "des données d’événements. Ce document décrit la preuve de concept (POC) d’un système "
            "RAG (Retrieval-Augmented Generation / génération de réponses augmentée par la recherche).",
        ),
        (
            "p",
            "Le POC devait démontrer la faisabilité technique avant une éventuelle industrialisation. "
            "Le périmètre géographique retenu est Paris. Seuls les événements de moins d’un an "
            "(historique de 12 mois et dates à venir) sont conservés, conformément à la demande du responsable technique.",
        ),
        ("h2", "2. Problématique"),
        (
            "p",
            "Un LLM seul connaît mal la programmation culturelle récente : il hallucine des dates, "
            "des salles ou des tarifs. À l’inverse, une recherche mot-clé sur un catalogue d’événements "
            "rate les formulations naturelles (« une expo calme ce week-end », « un concert jazz pas trop cher »). "
            "Le RAG combine les deux : recherche sémantique dans une base vectorielle, puis rédaction "
            "contrainte par les extraits trouvés.",
        ),
        ("bullet", "Source de vérité : API publique OpenAgenda (événements Parisiens)."),
        ("bullet", "Index local FAISS, reconstructible à la demande."),
        ("bullet", "Génération et embeddings via la plateforme Mistral, orchestrés par LangChain."),
        ("bullet", "Évaluation sur un jeu de questions/réponses annoté (même information / même sens)."),
        ("h2", "3. Architecture du système"),
        (
            "p",
            "Le système a deux phases. La phase d’indexation (hors ligne) récupère, filtre, découpe et vectorise "
            "les événements. La phase de question (en ligne) embarque la requête, interroge FAISS, construit un "
            "prompt augmenté et appelle le LLM Mistral. Aucun historique de conversation n’est utilisé dans le POC, "
            "comme demandé : chaque question est indépendante.",
        ),
        ("p", "Chaîne d’indexation : OpenAgenda → JSON brut → filtres Paris + fraîcheur → documents LangChain → chunks → mistral-embed → FAISS."),
        ("p", "Chaîne de question : texte utilisateur → embedding → top-k extraits FAISS → prompt système Puls-Events → ministral-8b-latest → réponse + sources affichées."),
        (
            "p",
            "Les métadonnées (titre, lieu, code postal, dates, URL) voyagent avec chaque chunk. Elles servent "
            "à la fois à l’affichage des sources dans la démo et aux tests unitaires de conformité du périmètre.",
        ),
        ("h2", "4. Collecte et préparation des données"),
        (
            "p",
            "La collecte s’appuie sur l’API REST OpenAgenda v2, authentifiée par clé publique de lecture. "
            "Le script tente d’abord une recherche transverse d’événements (filtre ville = Paris, événements "
            "en cours et à venir), puis complète via la découverte d’agendas officiels dont le titre ou le slug "
            "contient « Paris » (dont les slugs de type que-faire-a-paris).",
        ),
        (
            "p",
            "Chaque événement est normalisé : textes localisés (fr), HTML retiré, timings convertis en dates ISO, "
            "lieu, adresse, code postal, coordonnées GPS. Un événement est retenu s’il est localisé à Paris "
            "(nom de ville, code postal 75xxx, ou point GPS dans la boîte englobante intramuros) ET si sa dernière "
            "date est postérieure à aujourd’hui moins 365 jours. Les événements trop pauvres textuellement sont écartés.",
        ),
        (
            "p",
            f"Dans l’état actuel du POC, {ne} événements structurés sont disponibles pour l’indexation, "
            f"découpés en {nc} chunks. Exemples de lieux indexés : {venues}. "
            f"Thématiques observées : {kws}.",
        ),
        (
            "p",
            "Le découpage (chunking) utilise RecursiveCharacterTextSplitter de LangChain (1 200 caractères, "
            "chevauchement 150). Un événement court reste un seul chunk ; une longue description est fragmentée "
            "tout en conservant titre, lieu et dates dans les métadonnées de chaque fragment, pour ne pas perdre "
            "le contexte lors de la recherche.",
        ),
        ("h2", "5. Choix techniques"),
        (
            "p",
            "LangChain a été retenu parce que le brief l’impose et parce qu’il orchestre proprement retriever, "
            "prompt et LLM (LCEL). FAISS CPU (IndexFlatIP, similarité cosinus via vecteurs L2-normalisés côté "
            "LangChain/FAISS) convient au volume d’un POC : quelques centaines de vecteurs, recherche exacte, "
            "zéro infrastructure. Un index IVF ou HNSW n’apporterait rien à cette échelle et compliquerait "
            "la reconstruction.",
        ),
        (
            "p",
            "Mistral est utilisé de bout en bout : mistral-embed (dimension 1024) pour la vectorisation, "
            f"{CHAT_MODEL} pour la génération. Ce couplage évite un décalage de « langue vectorielle » entre "
            "l’index et le modèle de chat. ministral-8b-latest a été préféré à mistral-large pour le POC : "
            "coût et latence plus bas, français de bonne qualité, suffisant dès lors que le contexte RAG est pertinent. "
            "Un passage à un modèle plus grand reste un levier de la version finale.",
        ),
        (
            "p",
            "La démo live est le script ask.py : une question en ligne de commande, une réponse, les sources. "
            "Les secrets restent dans un fichier .env ignoré par Git. "
            "La reconstruction de l’index est un script unique (rebuild_index.py), reproductible dans un "
            "environnement virtuel documenté.",
        ),
        ("h2", "6. Modèles sélectionnés"),
        ("bullet", f"Embeddings : {EMBEDDING_MODEL} — texte d’événement → vecteur, recherche sémantique."),
        ("bullet", f"Génération : {CHAT_MODEL} — rédaction des recommandations à partir des extraits."),
        ("bullet", "Température 0,2 — réponses plutôt factuelles, peu créatives."),
        ("bullet", "k = 5 extraits — compromis entre couverture et bruit dans le prompt."),
        (
            "p",
            "Le prompt système impose le français, l’interdiction d’inventer des événements absents du contexte, "
            "et la restitution du titre, du lieu, des dates et de l’URL. Si le contexte est insuffisant, le modèle "
            "doit le dire. C’est le principal garde-fou anti-hallucination du POC.",
        ),
        ("h2", "7. Tests et évaluation"),
        (
            "p",
            "Les tests unitaires (tests/test_events_freshness.py) vérifient les filtres sur des événements synthétiques "
            "(Paris vs Lyon, date récente vs date trop ancienne) puis, lorsque les fichiers existent, parcourent "
            "le JSON traité et les métadonnées FAISS pour garantir que tout document indexé est bien à Paris et "
            "dans la fenêtre d’un an.",
        ),
        (
            "p",
            "Un jeu annoté de questions/réponses est généré à partir des événements réels (vérité terrain : titre, "
            "lieu, période). Selon le brief, une réponse du système est correcte si elle a le même sens et contient "
            "les mêmes informations que l’annotation humaine. L’évaluateur mesure la couverture des faits obligatoires "
            "(titre, lieu) dans la réponse générée.",
        ),
        (
            "p",
            f"Résultats du POC : {nq} questions annotées, accuracy retrieval = {acc}, "
            f"couverture moyenne des faits dans les extraits = {cov}. "
            "Le critère du brief (même sens / mêmes informations) est d’abord vérifié au niveau du retrieval : "
            "si le bon événement n’est pas dans le top-k, le LLM ne peut pas répondre correctement. "
            "L’évaluation des réponses générées (`python evaluate.py --llm`) dépend du quota de l’API Mistral "
            "(le palier gratuit peut renvoyer HTTP 429). Dans ce cas, la démo live reste valable dès que le quota se libère.",
        ),
        ("h2", "8. Résultats qualitatifs du POC"),
        (
            "p",
            "Le système répond de façon exploitable sur des questions du type « parle-moi de [titre] », "
            "« que se passe-t-il à [salle] », ou « une sortie dans le 75011 ». Les sources s’affichent sous "
            "la réponse, ce qui permet à un product owner de vérifier l’origine OpenAgenda. La reconstruction "
            "de l’index tient en une commande. L’environnement se installe via requirements.txt.",
        ),
        (
            "p",
            "Limites assumées du POC : pas de mémoire de dialogue, pas de filtre date interactif dans l’UI "
            "(la fraîcheur est garantie à l’indexation), volume plafonné (MAX_EVENTS) pour rester dans le quota "
            "gratuit Mistral, dépendance réseau aux deux API, et similarité sémantique brute sans reranker.",
        ),
        ("h2", "9. Recommandations pour la version finale"),
        ("bullet", "Filtres métadonnées au moment de la recherche : arrondissement, intervalle de dates, gratuit/payant, type d’événement."),
        ("bullet", "Recherche hybride (mots-clés BM25 + vecteurs) pour les titres propres et les noms de salles."),
        ("bullet", "Reranker (modèle croisé) sur les 20 premiers extraits avant le LLM."),
        ("bullet", "Quota et cache d’embeddings : ne re-vectoriser que les événements nouveaux ou modifiés."),
        ("bullet", "Observabilité : journaliser question, extraits, réponse, et un score de fidélité au contexte."),
        ("bullet", "Jeu annoté enrichi manuellement par l’équipe produit (20–50 questions représentatives des vrais utilisateurs)."),
        ("bullet", "Passer à un modèle Mistral plus capable si les réponses manquent de synthèse, tout en gardant une température basse."),
        ("bullet", "Déploiement : API FastAPI derrière le front Puls-Events, index FAISS ou bascule vers un moteur managé si le catalogue dépasse ~100k chunks."),
        ("bullet", "Conformité : licences OpenAgenda, mentions des sources, pas de stockage inutile de données personnelles."),
        ("h2", "10. Conclusion"),
        (
            "p",
            "Le POC démontre qu’un assistant de recommandation culturelle, ancré dans OpenAgenda et limité à Paris "
            "sur une fenêtre d’un an, est réalisable avec la pile imposée LangChain + Mistral + FAISS, entièrement "
            "reproductible en local. La génération augmentée réduit les hallucinations par rapport à un LLM nu, "
            "à condition que le retrieval soit pertinent. Les prochains investissements doivent porter sur les filtres, "
            "le reranking et l’évaluation produit, plus que sur un changement d’infrastructure.",
        ),
        ("h2", "Annexes"),
        ("bullet", "Commandes : python check_setup.py · python rebuild_index.py · pytest · python ask.py \"…\" · python evaluate.py"),
        ("bullet", "Fichiers clés : src/pulsevents/ · tests/test_events_freshness.py · data/evaluation/annotated_qa.json"),
        ("bullet", "Secrets : fichier .env (jamais versionné)."),
    ]


def write_markdown(stats: dict) -> Path:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    path = DOCS_DIR / "rapport.md"
    lines = []
    for style, text in report_paragraphs(stats):
        if style == "h1":
            lines.append(f"# {text}\n")
        elif style == "h2":
            lines.append(f"\n## {text}\n")
        elif style == "bullet":
            lines.append(f"- {text}")
        else:
            lines.append(text + "\n")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_docx(stats: dict) -> Path:
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)

    for style, text in report_paragraphs(stats):
        if style == "h1":
            p = doc.add_heading(text, level=0)
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        elif style == "h2":
            doc.add_heading(text, level=1)
        elif style == "bullet":
            doc.add_paragraph(text, style="List Bullet")
        else:
            p = doc.add_paragraph(text)
            p.paragraph_format.space_after = Pt(8)
            for run in p.runs:
                run.font.size = Pt(11)
                run.font.name = "Calibri"
    path = DOCS_DIR / "rapport.docx"
    doc.save(path)
    return path


def _find_font() -> tuple[Path | None, Path | None]:
    regular = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
    bold = Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")
    if regular.exists() and bold.exists():
        return regular, bold
    georgia = Path("/System/Library/Fonts/Supplemental/Georgia.ttf")
    if georgia.exists():
        return georgia, georgia
    return None, None


def write_pdf(stats: dict) -> Path:
    regular, bold = _find_font()
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(18, 18, 18)
    pdf.add_page()
    if regular:
        pdf.add_font("Body", "", str(regular))
        pdf.add_font("Body", "B", str(bold or regular))
        font = "Body"
    else:
        font = "Helvetica"

    usable = pdf.w - pdf.l_margin - pdf.r_margin

    def write_block(style: str, text: str, size: int, height: float) -> None:
        pdf.set_x(pdf.l_margin)
        pdf.set_font(font, style, size)
        pdf.multi_cell(usable, height, text)

    for style, text in report_paragraphs(stats):
        safe = text.replace("•", "-")
        if style == "h1":
            write_block("B", safe, 16, 9)
            pdf.ln(2)
        elif style == "h2":
            pdf.ln(3)
            write_block("B", safe, 13, 8)
            pdf.ln(1)
        elif style == "bullet":
            write_block("", f"- {safe}", 11, 6)
        else:
            write_block("", safe, 11, 6)
            pdf.ln(1)
    path = DOCS_DIR / "rapport.pdf"
    pdf.output(str(path))
    return path


NAVY = RGBColor(0x1B, 0x3A, 0x4B)
TEAL = RGBColor(0x2A, 0x9D, 0x8F)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DARK = RGBColor(0x1F, 0x1F, 0x1F)


def _slide_bg(slide, color: RGBColor) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_text(slide, left, top, width, height, text, size=18, bold=False, color=DARK, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = PptPt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = "Calibri"
    return tf


def write_pptx(stats: dict) -> Path:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    def new_content_slide(kicker: str, title: str):
        slide = prs.slides.add_slide(blank)
        _slide_bg(slide, WHITE)
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(0.18))
        shape.fill.solid()
        shape.fill.fore_color.rgb = TEAL
        shape.line.fill.background()
        _add_text(slide, 0.7, 0.35, 12, 0.35, kicker, size=12, bold=True, color=TEAL)
        _add_text(slide, 0.7, 0.65, 12, 0.7, title, size=28, bold=True, color=NAVY)
        return slide

    # 1 titre
    s = prs.slides.add_slide(blank)
    _slide_bg(s, NAVY)
    _add_text(s, 0.8, 2.0, 11, 0.4, "PULS-EVENTS  ·  PREUVE DE CONCEPT", 14, True, TEAL)
    _add_text(s, 0.8, 2.5, 11.5, 1.4, "Assistant de recommandation\nd’événements culturels", 36, True, WHITE)
    _add_text(
        s,
        0.8,
        5.2,
        11,
        1.2,
        f"RAG · LangChain · Mistral · FAISS\nPérimètre : {stats['city']} · événements < 12 mois · {stats['date']}",
        16,
        False,
        WHITE,
    )

    # 2 contexte
    s = new_content_slide("01  CONTEXTE", "Pourquoi Puls-Events teste un chatbot")
    _add_text(
        s,
        0.7,
        1.6,
        12,
        5,
        "Puls-Events agrège l’offre culturelle (OpenAgenda) et veut un assistant capable\n"
        "de recommander des sorties adaptées, filtrables par lieu et par période.\n\n"
        "Objectif du POC : montrer à Produit et Marketing qu’une génération augmentée\n"
        "(AGR / RAG) ancrée dans une base vectorielle est faisable, évaluable, et démoable.",
        20,
        False,
        DARK,
    )

    # 3 problème
    s = new_content_slide("02  PROBLÈME", "Un LLM seul n’est pas un agenda")
    bullets = [
        "Il invente des dates, des salles, des tarifs (hallucinations).",
        "Le catalogue Puls-Events change tous les jours : le modèle n’est pas à jour.",
        "Une recherche mot-clé rate le langage naturel des utilisateurs.",
        "Il faut une réponse sourcée, vérifiable en réunion de go / no-go.",
    ]
    _add_text(s, 0.7, 1.6, 12, 5, "\n\n".join(f"•  {b}" for b in bullets), 20)

    # 4 solution
    s = new_content_slide("03  SOLUTION", "RAG : chercher d’abord, rédiger ensuite")
    _add_text(
        s,
        0.7,
        1.6,
        12,
        5,
        "1.  Indexer les événements Paris (moins d’un an) sous forme de vecteurs.\n\n"
        "2.  À chaque question, retrouver les extraits sémantiquement proches.\n\n"
        "3.  Demander à Mistral de répondre UNIQUEMENT avec ces extraits.\n\n"
        "Résultat : recommandation rédigée + sources OpenAgenda affichées.",
        20,
    )

    # 5 architecture
    s = new_content_slide("04  ARCHITECTURE", "Deux phases, tout le code en local")
    _add_text(
        s,
        0.7,
        1.6,
        12,
        5.2,
        "Indexation (à la demande)\n"
        "OpenAgenda  →  filtres Paris + 12 mois  →  chunks  →  mistral-embed  →  FAISS\n\n"
        "Question (démo live)\n"
        "utilisateur  →  embedding  →  top-5 FAISS  →  prompt  →  mistral-small  →  réponse\n\n"
        "Pas de GPU, pas de cloud applicatif. Deux API externes : OpenAgenda et Mistral.",
        18,
    )

    # 6 données
    s = new_content_slide("05  DONNÉES", f"OpenAgenda · {stats['city']}")
    _add_text(
        s,
        0.7,
        1.6,
        12,
        5,
        f"•  {stats['n_events']} événements structurés après filtrage\n"
        f"•  {stats['n_chunks']} chunks indexés dans FAISS\n"
        "•  Ville = Paris (nom, CP 75xxx ou GPS intramuros)\n"
        "•  Dates : dernière occurrence ≥ aujourd’hui − 365 jours, plus le futur\n"
        f"•  Lieux exemples : {', '.join(stats['venues'][:6]) or 'selon collecte'}",
        20,
    )

    # 7 stack
    s = new_content_slide("06  CHOIX TECHNIQUES", "La pile imposée, utilisée vraiment")
    _add_text(
        s,
        0.7,
        1.6,
        12,
        5,
        "•  LangChain : orchestration retriever → prompt → LLM\n"
        "•  FAISS CPU : index local exact, reconstructible (rebuild_index.py)\n"
        f"•  {EMBEDDING_MODEL} : vecteurs d’événements\n"
        f"•  {CHAT_MODEL} : rédaction, température 0,2\n"
        "•  ask.py : démo live en ligne de commande\n"
        "•  Pytest : conformité Paris + fraîcheur < 1 an",
        20,
    )

    # 8 modèles
    s = new_content_slide("07  MODÈLES", "Pourquoi small plutôt que large")
    _add_text(
        s,
        0.7,
        1.6,
        12,
        5,
        "Le goulot d’un RAG n’est pas la taille du LLM, c’est la qualité du chunk ramené.\n\n"
        "ministral-8b-latest : français solide, coût et latence adaptés à une démo.\n"
        "mistral-embed : même écosystème, 1024 dimensions, standard Mistral.\n\n"
        "Version finale : tester un modèle plus grand seulement si la synthèse reste pauvre\n"
        "malgré un bon retrieval.",
        20,
    )

    # 9 résultats
    s = new_content_slide("08  RÉSULTATS DU POC", "Ce qui a été mesuré")
    _add_text(
        s,
        0.7,
        1.6,
        12,
        5,
        f"•  Jeu annoté : {stats['n_questions']} questions (titre, thème, lieu, quartier)\n"
        f"•  Accuracy retrieval (faits annotés présents dans le top-k) : {stats['accuracy']}\n"
        f"•  Couverture moyenne des faits : {stats['coverage']}\n\n"
        "Critère du brief : même sens + mêmes informations que la réponse humaine.\n"
        "Si le quota chat Mistral est saturé (429), lancer `python evaluate.py --llm` plus tard.\n"
        "Les sources s’affichent sous chaque réponse de la démo.",
        20,
    )

    # 10 démo
    s = new_content_slide("09  DÉMO LIVE", "Ce que nous allons montrer")
    _add_text(
        s,
        0.7,
        1.6,
        12,
        5,
        "1.  Reconstruction de l’index (commande unique).\n"
        "2.  Question ciblée sur un titre d’événement réel.\n"
        "3.  Question ouverte (« expo », « concert », « sortie familiale »).\n"
        "4.  Affichage des extraits OpenAgenda (preuve que ce n’est pas du bluff).\n"
        "5.  Une question hors périmètre → le bot refuse d’inventer.",
        20,
    )

    # 11 limites
    s = new_content_slide("10  LIMITES", "Honnêteté de POC")
    _add_text(
        s,
        0.7,
        1.6,
        12,
        5,
        "•  Pas de mémoire de conversation (choix du brief).\n"
        "•  Volume plafonné pour rester dans le quota API.\n"
        "•  Pas de filtre date interactif dans l’UI (filtre à l’indexation seulement).\n"
        "•  Similarité brute, sans reranker.\n"
        "•  Dépendance réseau Mistral + OpenAgenda.",
        20,
    )

    # 12 reco
    s = new_content_slide("11  VERSION FINALE", "Recommandations")
    _add_text(
        s,
        0.7,
        1.6,
        12,
        5.2,
        "•  Filtres métadonnées : dates, arrondissement, prix, type\n"
        "•  Hybride BM25 + vecteurs + reranker\n"
        "•  Cache d’embeddings et MAJ incrémentale du catalogue\n"
        "•  Jeu annoté enrichi par Produit (vrais parcours utilisateurs)\n"
        "•  API derrière le front Puls-Events, observabilité des hallucinations\n"
        "•  FAISS tant que le volume est petit ; moteur managé au-delà",
        20,
    )

    # 13 conclusion
    s = prs.slides.add_slide(blank)
    _slide_bg(s, NAVY)
    _add_text(s, 0.8, 2.3, 11.5, 0.4, "12  CONCLUSION", 14, True, TEAL)
    _add_text(
        s,
        0.8,
        2.8,
        11.5,
        2.5,
        "Le POC est fonctionnel, reproductible et démontrable.\n"
        "La pile LangChain + Mistral + FAISS suffit pour décider d’un go.\n"
        "L’enjeu suivant est produit : filtres, qualité de retrieval, évaluation.",
        24,
        True,
        WHITE,
    )

    path = DOCS_DIR / "presentation.pptx"
    prs.save(path)
    return path


def main() -> None:
    stats = load_stats()
    md = write_markdown(stats)
    docx = write_docx(stats)
    pdf = write_pdf(stats)
    pptx = write_pptx(stats)
    print("Généré :")
    for path in (md, docx, pdf, pptx):
        print(" -", path)


if __name__ == "__main__":
    main()
