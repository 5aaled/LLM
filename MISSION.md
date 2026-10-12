# Mission — Develop an assistant for recommending cultural events

This is the original brief (saved next to the project README).  
The working POC that answers it lives in this `project/` folder. How to run it: [`README.md`](./README.md).

---

## How to proceed

This mission follows a professional project scenario. You can follow the steps to help you achieve your deliverables.

Before you start:

- read the entire mission and its related documents
- take notes on what you understand
- consult the steps to guide you
- prepare a list of questions for your first mentoring session

This project is toward the end of the course and does not contain a self-assessment sheet. It is fully guided: follow the steps below.

---

## Context

You are a freelance data engineer specializing in NLP model integration and vector database management. You work for **Puls-Events**, an innovative company in cultural event management.

Puls-Events offers a web platform that lets users discover and follow cultural events in real time. It collects information from various sources, such as **OpenAgenda**, to offer events adapted to user preferences, filterable by location and period.

The company wants to test an intelligent chatbot that can give personalized recommendations, **augmented with precise answers from event data**.

The chatbot, supported by a **RAG** system (Retrieval-Augmented Generation — also called AGR / génération de réponses augmentée), must extract and analyze information from a **vector database**.

You are responsible for a first **Proof of Concept (POC)** to show that this is feasible.

---

## Message from the technical manager

**From:** Jeremy  
**To:** me  
**Subject:** functional version of the POC RAG

Hi,

We need you to complete a working version of the POC RAG. It will be presented in a meeting with the product and marketing teams to verify the interest of the project and consider its deployment on a larger scale.

As discussed together, we will rely on the **public events** data source **OpenAgenda**. You can limit yourself to a **geographic scope of your choice**. However, make sure that there are only **recent events of less than a year**.

What is expected:

1. **Virtual environment** — To make the project easily reproducible: dependencies and documentation in the form of a README.
2. **Functional RAG system** — Complete RAG system code versioned in a git repo, with integration of **LangChain**, **Mistral** and **FAISS**. The system must be able to **reconstruct the vector base on request** (pre-processing and data vectorization scripts).
3. **Technical report (PDF or Word)** — Document between **5 and 10 pages**, explaining the architecture of the system, your technical choices, the models selected, the results obtained for the POC and the recommendations for the final version.
4. **Unit testing (Python)** — Provide a `.py` file to test that the data integrated into the vector database corresponds to events **less than a year old** in the **geographical region you have selected**.
5. **Presentation (PowerPoint)** — Between **10 and 15 slides** to present the concept of the project and the results of the POC.
6. **Live demo of the system** — Prepare a live demo to illustrate the capabilities of the POC.

Don't hesitate if you need details on the scope or expectations. We're counting on you to get everything ready on time!

Oh yes, I forgot. To evaluate the system, we will need to create an **annotated test dataset of questions/answers**. This test set will be used to measure the quality of responses against annotated responses.

Thank you and good luck!

Jeremy

---

## Guided steps

### Step A — Configure the development environment

Configure the development environment necessary to implement the RAG system. Install the required libraries, and make sure everything works correctly.

**Prerequisites**

- Have installed the LangChain and FAISS libraries.

**Expected result**

A functional development environment with all tools installed and ready to use.

**Recommendations**

- Start by creating a virtual environment.
- Install the required packages: `pip install langchain faiss-cpu mistral`.
- Test that all installations are correct by running a simple Python script to import the required libraries.

**Points of vigilance**

- Check that all versions of the packages are compatible.
- Make sure FAISS is installed with the **CPU** backend to avoid errors.

**Tools:** Python 3 · LangChain · FAISS · Mistral API · virtualenv or conda

---

### Step B — Retrieve, filter, and structure event data

Retrieve event data from the OpenAgenda platform, filter it by location and time period, and structure this data for future use in the vector database.

**Prerequisites**

- Have access to the OpenAgenda API.
- Have understood the desired filtering parameters (city, period, type of event).

**Expected result**

A clean, structured event dataset, ready for indexing. You will be able to perform unit tests to ensure you have recovered the expected data.

**Recommendations**

- Use the OpenAgenda API to retrieve events.
- Filter events by location and period (**1 year history and upcoming events**).
- Convert event descriptions to vector format with an NLP model like Mistral.

**Points of vigilance**

- Beware of missing or incorrect data.
- Check the relevance of filters so that events are well targeted.

**Tools:** OpenAgenda API · Pandas for data manipulation · Mistral for vector generation

---

### Step C — Index events in FAISS

Index event descriptions as vectors in a vector database with FAISS, allowing rapid searching based on semantic similarity.

**Prerequisites**

- Have cleaned OpenAgenda data.
- Have divided the texts into **chunks** before vectorizing the texts.
- Vectorization of each chunk and indexing in the FAISS database.

**Expected result**

A FAISS database containing events indexed according to their semantic vectors.

**Recommendations**

- Use FAISS to build a semantic search index.
- Record information not only about vectors, but also about event **metadata** (dates, locations, descriptions).
- Do research tests to check effectiveness.

**Points of vigilance**

- Make sure the index is optimized for quick searches (use the correct algorithms in FAISS).
- Check that all events have been indexed correctly.

**Tools:** FAISS for vector indexing · LangChain to interact with FAISS

---

### Step D — Develop the chatbot

Develop the intelligent chatbot capable of providing personalized recommendations based on indexed events, and generate augmented responses from data present in the vector database.

**Prerequisites**

- Events are indexed in FAISS.
- Mistral API to generate natural responses from a selected LLM on the Mistral platform.

**Expected result**

A chatbot capable of providing event recommendations and interacting with the user.

An AI response is **correct** if it has the **same meaning** and contains the **same information** as the human-annotated response.

**Recommendations**

- Use LangChain to orchestrate calls between the FAISS database and the Mistral model.
- Configure processing chains so that the chatbot can generate responses based on both the search in FAISS and the language model.

**Points of vigilance**

- Ensure that the responses generated are both relevant and well formulated.
- Test multiple interaction scenarios to verify chatbot robustness.
- **Conversation history between bot and human is not needed in the POC.**

**Tools:** LangChain for interaction management · Mistral for generating responses

---

## Where each expected item lives in this repo

Scope chosen for the POC: **Paris**, events **less than one year old** (12 months of history + upcoming).

| Expected by Jeremy | In this project |
| --- | --- |
| Virtual environment + README | `.venv/`, `requirements.txt`, [`README.md`](./README.md), `check_setup.py` |
| RAG code + Git | `src/pulsevents/`, `rebuild_index.py`, `ask.py` |
| Reconstruct the vector base on request | `python rebuild_index.py` |
| LangChain + Mistral + FAISS | `rag.py`, `index.py`, `requirements.txt` |
| Technical report 5–10 pages | `docs/rapport.md`, `docs/rapport.docx`, `docs/rapport.pdf` |
| Unit tests: Paris + less than 1 year | `tests/test_events_freshness.py` |
| Presentation 10–15 slides | `docs/presentation.pptx` |
| Live demo | `python ask.py "Propose-moi un concert à Paris"` |
| Annotated Q/A dataset | `data/evaluation/annotated_qa.json`, `evaluate.py` |
