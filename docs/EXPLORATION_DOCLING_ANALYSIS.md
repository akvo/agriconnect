# Exploration Note: Document Ingestion Engine — Docling Technical Evaluation

> **Status:** Draft / Exploration Note  
> **Context:** AkvoConnect Phase 3 (Multi-Tenancy, Multi-Sector, Multimodal Pump Diagnostics)  
> **Target System:** Akvo RAG Ingestion Pipeline  
> **Author:** Engineering Team  

---

## 1. Executive Summary

In AkvoConnect Phase 3, incoming Knowledge Base content changes drastically from simple agricultural guidance text to complex, visual-heavy technical manuals:
- **UNICEF & WaterNet (Water Sector):** Operation & Maintenance (O&M) manuals with pump mechanical diagrams, spare part breakdowns, flowchart decision trees, and assembly photos.
- **Johns Hopkins University (Health Sector):** Clinical and public health guidelines with complex medical dosage tables, schedules, and clinical protocols.

Standard parsers (PyPDF, PDFMiner, basic text converters) destroy table column alignments and discard figures. **IBM Docling (`docling.ai`)** is evaluated as the core ingestion engine to convert PDF, DOCX, and PPTX documents into structured, layout-aware Markdown/JSON with native image/diagram extraction.

Because Docling is **100% open-source (Linux Foundation / Apache-2.0)** and runs locally inside Akvo's infrastructure, **there are zero recurring AI API or per-page token fees**.

This document details the architectural capabilities, pros/cons, and implementation recommendations for adopting Docling in Akvo RAG.

---

## 2. Core Value Proposition of Docling for Akvo RAG

### 2.1. Advanced Table Understanding (`TableFormer`)
Technical and health manuals frequently feature multi-row headers, merged cells, and borderless tables. Docling's deep-learning model (`TableFormer`) reconstructs complex tables into structured Markdown and JSON representations, allowing the RAG LLM to accurately answer queries like:
> *"What is the bolt size and torque specification for an Afridev pump cylinder?"*

### 2.2. Multimodal Figure & Diagram Extraction (Key for Pump Diagnostics)
Unlike converters that simply strip or flatten embedded visuals:
- Docling identifies figures, diagrams, and illustrations across **PDF, DOCX, and PPTX**.
- It crops and exports the visual assets while preserving their bounding context (captions, parent section, surrounding explanatory paragraphs).
- These extracted figures populate the **Qdrant visual vector index** (via CLIP/SigLIP embeddings) to enable reverse image lookups when citizens send photos of broken pumps via WhatsApp.

### 2.3. Unified Document Object Model (DOM) & Layout-Aware Chunking
Docling recognizes reading order, headings, footnotes, and callout warning blocks across file formats. Chunking logic in Akvo RAG respects document semantics rather than splitting arbitrarily across token boundaries.

---

## 3. Infrastructure & Deployment Model (Aligning with Akvo RAG Monorepo)

Following the modern architecture established in **`akvo/akvo-rag` PR #163** (which eliminated Celery/RabbitMQ in favor of native asynchronous Redis queues):

- **Zero AI Licensing / Token Cost:** All parsing, table extraction, and figure crops are executed locally by Docling's built-in models. No external AI APIs are billed during ingestion.
- **Native Redis Ingestion Worker (No Celery Needed):** Document ingestion is processed by the dedicated **`vector-kb-mcp-ingestion`** worker service listening to the Redis Ingestion Queue.
- **Storage Pipeline:** Raw documents and cropped diagram images are stored directly in **MinIO S3**, while structured chunks and embeddings are pushed to the vector database.
- **Hardware Profile:** Runs efficiently on standard CPU compute (recommended: 4 vCPU, 8 GB RAM), processing ~20–40 pages per minute without requiring dedicated GPU hardware.

---

## 4. Pros and Cons Matrix

### Pros
1. **Zero Recurring AI / Per-Page Fees:** Complete data sovereignty and predictable operational costs regardless of how many manuals partners upload.
2. **Unified Multimodal Pipeline:** Extracts text, tables, and images uniformly across PDF, DOCX, and PPTX.
3. **Structured Export:** Produces clean Markdown and JSON with native metadata ready for vector database payload indexing.
4. **Native MCP & Redis Compatibility:** Seamlessly integrates into `akvo-rag`'s Redis queue worker architecture (`vector-kb-mcp-ingestion`) without adding Celery dependencies.

### Cons & Mitigations
1. **Container Size:** The Docker image for the ingestion worker is large (~2.5–3.5 GB) due to PyTorch and model weights.
   - *Mitigation:* Already aligned with PR #163's architecture—the ingestion worker runs in its own isolated Docker container (`vector-kb-mcp-ingestion`), keeping the main FastAPI backend lightweight.
2. **CPU-Intensive Ingestion:** Parsing complex PDFs without a GPU takes several seconds per page.
   - *Mitigation:* Decoupled into the asynchronous Redis ingestion worker; the client receives a job ID immediately and tracks progress via callbacks.

---

## 5. Implementation Recommendation

1. **Adopt Docling** as the core parsing engine inside the **`vector-kb-mcp-ingestion`** container of `akvo-rag`.
2. **Utilize Native Redis Ingestion Consumer:** Keep the existing PR #163 queue consumer architecture (no Celery required).
3. **Store Visual Assets in MinIO S3:** Save cropped pump diagrams and charts to MinIO and index their embeddings alongside text chunks for multimodal retrieval.
