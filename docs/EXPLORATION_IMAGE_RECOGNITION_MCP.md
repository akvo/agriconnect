# Exploration Note: Akvo RAG Image Recognition Architecture & MCP Integration

> **Status:** Draft / Exploration Note  
> **Context:** AkvoConnect Phase 3 (Multi-Tenancy, Water/WASH Sector, Photo-Based Pump Diagnostics)  
> **Target Systems:** AgriConnect Backend & Akvo RAG Monorepo (aligned with PR #163)  
> **Author:** Engineering Team  

---

## 1. Executive Summary

In AkvoConnect Phase 3, one of the headline capabilities for the Water/WASH sector (partnered with UNICEF & WaterNet) is **photo-based pump diagnostics**. When rural water point caretakers encounter broken handpumps (e.g., Afridev or India Mark II), they frequently cannot describe the mechanical failure accurately through text alone.

### Key Architectural Decisions:
1. **Zero S3 Infrastructure in AgriConnect:** AgriConnect remains lightweight and stateless regarding permanent object storage. It simply forwards image bytes via `multipart/form-data` to the established `chat_url`. **Akvo RAG alone manages MinIO S3** for persistent storage and pre-signed URL generation.
2. **Reuse Existing Chat Endpoint:** No new endpoints (`/api/v1/query/image`) are introduced. AgriConnect uses the existing `chat_url` and callback webhook (`/api/callback/ai`).
3. **Alignment with PR #163:** Native monorepo integration utilizing `MCPQueueDispatcher`, Redis Request-Reply queues, MinIO S3 (:9010), and dedicated `vector-kb-mcp` worker services.
4. **Dual Image Lifecycle (Ingestion vs. Query):**
   - **Knowledge Base Images:** Sourced automatically via **Docling** from partner manuals (PDF/DOCX/PPTX) and cataloged into MinIO + Qdrant.
   - **Query Images:** Sent by citizens via WhatsApp, interpreted by a **Vision LLM** into structured diagnostic queries, and matched against the Docling-extracted knowledge base.

---

## 2. Complete Visual Workflow (Citizen-First Flowchart)

The following flowchart shows the end-to-end journey starting directly from **the citizen taking a photo of a broken pump** and following through to diagnostic retrieval:

```mermaid
flowchart TD
    %% Citizen & AgriConnect
    USER(["👤 Citizen / Caretaker<br/>Takes photo of broken handpump"]):::userNode
    USER -->|"1. Sends photo & message via WhatsApp"| AGRI["AgriConnect Backend (:8000)<br/>- Inbound webhook receiver<br/>- Extracts multipart image stream"]:::agriNode
    
    %% Forward to Akvo RAG
    AGRI -->|"2. POST chat_url (multipart: payload + image)"| RAG["Akvo RAG Backend (:8010)<br/>- Reuses existing chat endpoint<br/>- Receives image stream"]:::ragNode

    %% Akvo RAG Storage & Queueing
    subgraph STAGE_LAYER["Akvo RAG Staging & Messaging (PR #163)"]
        direction TB
        RAG -->|"3. Save raw photo"| MINIO_RAW[("MinIO S3 (:9010)<br/>bucket: raw-uploads/")]:::s3Node
        RAG -->|"4. Dispatch task with correlation_id"| REDIS_Q[("Redis RPC Queue<br/>queue:mcp:vision_query")]:::redisNode
    end

    %% Worker Processing
    REDIS_Q -->|"5. Consume task"| WORKER["Worker: vector-kb-mcp<br/>(Vision Recognition Tool)"]:::workerNode
    MINIO_RAW -.->|"Fetch photo URL"| WORKER

    %% Vision LLM Analysis
    subgraph VISION_INFERENCE["Visual Analysis"]
        direction TB
        WORKER -->|"6. Send photo + JSON schema prompt"| VLLM["Vision LLM (OpenAI GPT-4o / Gemini)"]:::vllmNode
        VLLM -->|"7. Return structured analysis"| DETECT["Detected: Afridev Handpump<br/>Fault: Fractured fulcrum pin bracket<br/>Search Query: 'Afridev fulcrum pin replacement'"]:::detectNode
    end

    %% Knowledge Retrieval
    subgraph KB_SEARCH["Knowledge Base Retrieval"]
        direction TB
        DETECT -->|"8. Vectorize search query (1536d)"| QDRANT[("Vector DB (Qdrant)<br/>Scoped: tenant_id='unicef-water' & sector='water'")]:::qdrantNode
        QDRANT -->|"9. Return matched O&M guide & diagrams"| SOLUTION["Assembled Diagnosis & Solution:<br/>• Step-by-step repair instructions<br/>• Tool specifications (17mm wrench)<br/>• MinIO diagram schematic link"]:::solNode
    end

    %% Response Delivery
    SOLUTION -->|"10. Publish reply to Redis"| REDIS_RES[("Redis Response Channel<br/>response:correlation_id")]:::redisNode
    REDIS_RES --> RAG
    RAG -->|"11. Webhook Callback (POST /api/callback/ai)"| AGRI
    AGRI -->|"12. WhatsApp reply with repair steps & diagram"| USER_RECEIVE(["👤 Citizen receives repair guide & schematic diagram on phone"]):::userNode

    %% Styling Classes
    classDef userNode fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#0369a1;
    classDef agriNode fill:#ecfdf5,stroke:#059669,stroke-width:2px,color:#065f46;
    classDef ragNode fill:#fffbeb,stroke:#d97706,stroke-width:2px,color:#92400e;
    classDef s3Node fill:#fdf2f8,stroke:#db2777,stroke-width:2px,color:#9d174d;
    classDef redisNode fill:#fef2f2,stroke:#dc2626,stroke-width:2px,color:#991b1b;
    classDef workerNode fill:#f5f3ff,stroke:#7c3aed,stroke-width:2px,color:#5b21b6;
    classDef vllmNode fill:#ecfeff,stroke:#0891b2,stroke-width:2px,color:#155e75;
    classDef detectNode fill:#f8fafc,stroke:#475569,stroke-width:1.5px,color:#1e293b;
    classDef qdrantNode fill:#eef2ff,stroke:#4f46e5,stroke-width:2px,color:#3730a3;
    classDef solNode fill:#f0fdf4,stroke:#16a34a,stroke-width:2px,color:#14532d;
```

---

### 2.2. Offline Background Ingestion: How Knowledge Base Diagrams are Created
This offline pipeline populates the multimodal Knowledge Base with technical diagrams before citizens ask questions:

```mermaid
flowchart TD
    A["Partner Admin uploads O&M Manual<br/>(PDF, DOCX, PPTX)"] --> B["Akvo RAG Backend (:8010)"]
    B -->|Dispatch Ingestion Task| C[("Redis Ingestion Queue")]
    C --> D["Worker: vector-kb-mcp-ingestion"]
    
    subgraph Docling_Processing["Docling Processing Engine"]
        D --> E["IBM Docling Parser"]
        E -->|Layout & TableFormer| F["Structured Markdown & Tables"]
        E -->|Figure & Diagram Extraction| G["Mechanical Schematics & Part Images"]
    end
    
    G -->|Store Visual Assets| H[("MinIO S3 (:9010)<br/>bucket: kb-diagrams/")]
    H -->|Return Diagram URL| I["Bind Diagram Metadata<br/>(caption, section, model)"]
    
    F --> J["Text Embedder<br/>(text-embedding-3-small)"]
    I --> J
    
    J -->|Named Vectors + Payload| K[("Vector DB (Qdrant)<br/>tenant_id: unicef-water<br/>sector: water")]
```

---

## 3. End-to-End Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor C as Citizen / Caretaker
    participant AC as AgriConnect Backend (:8000)
    participant AR as Akvo RAG Backend (:8010)
    participant MIN as MinIO S3 Storage (:9010)
    participant RED as Redis Queue (:6379)
    participant VKB as vector-kb-mcp (Worker)
    participant VLLM as Vision LLM (OpenAI / Gemini)
    participant VDB as Vector DB (Qdrant / Chroma)

    C->>AC: Send WhatsApp photo + note: "Pump handle is stuck"
    Note over AC,AR: AgriConnect does NOT need S3. Forwards bytes directly via multipart.
    AC->>AR: POST existing chat_url (form_data: payload + image file)
    AR->>MIN: Store upload (tenant-{id}-uploads/pumps/raw_{uuid}.jpg)
    AR->>RED: MCPQueueDispatcher.send(queue:mcp:vision_query, correlation_id)
    
    RED->>VKB: Consumer picks up task
    VKB->>MIN: Fetch image presigned URL
    VKB->>VLLM: Analyze pump image with structured schema prompt
    VLLM-->>VKB: JSON (model: Afridev, component: pivot pin, defect: fracture, search_query)
    
    VKB->>VDB: Query Vector DB (filter: tenant_id="unicef-water", sector="water")
    VDB-->>VKB: Matched O&M steps + Docling-extracted diagram URLs
    
    VKB->>RED: Publish response to response:{correlation_id}
    RED->>AR: Akvo RAG receives completed diagnosis
    AR->>AC: POST webhook callback (/api/callback/ai)
    AC-->>C: WhatsApp reply with diagnosis, step-by-step fix & diagram image
```

---

## 4. Deep-Dive: Storage & Knowledge Base Strategy

### 4.1. Why AgriConnect Does Not Need S3
1. **Separation of Concerns:** AgriConnect handles channel routing, customer profiles, tickets, and officer assignment. Permanent media storage, chunking, and AI embeddings belong strictly inside Akvo RAG.
2. **Zero Infrastructure Duplication:** Akvo RAG already bundles MinIO S3 (:9010) in its Docker Compose setup (PR #163). Adding S3 to AgriConnect would duplicate AWS/MinIO credentials, bucket lifecycles, and storage sync logic.
3. **Stateless Forwarding:** AgriConnect receives media bytes from the WhatsApp/Meta webhook and streams them directly to Akvo RAG's `chat_url` via `httpx`.

### 4.2. How the Image Knowledge Base Works
The Knowledge Base for images is not built manually; it is constructed through two complementary ingestion mechanisms:

#### 1. Automatic Document Diagram Extraction (Docling)
- During partner manual upload (PDF/DOCX/PPTX), **Docling** extracts embedded mechanical schematics, part callouts, and repair flowcharts.
- Each extracted image is saved to MinIO (`kb-diagrams/{tenant_id}/{doc_id}/fig_{n}.png`).
- The image is paired with its surrounding text context (caption, section heading, parent paragraphs) and indexed in Qdrant with `tenant_id` metadata.

#### 2. Partner Spare Part Reference Catalog (Admin Upload)
- Partners (UNICEF, WaterNet) can optionally upload an image bank of certified spare parts and common failure modes (e.g., 50 sample photos of worn-out vs. new rubber seals).
- Stored as reference assets in MinIO and registered in the Knowledge Base table.

### 4.3. Retrieval Strategies: Text-Bridge vs. Direct Visual Matching

| Strategy | How it Works | Pros | Current Recommendation |
| :--- | :--- | :--- | :--- |
| **Strategy A: Text-Bridge Retrieval** | Vision LLM inspects citizen photo ➔ produces structured technical text query ➔ searches Docling-extracted text chunks and diagram URLs in Qdrant. | Highest semantic accuracy; handles fuzzy/dirty camera shots; explains *why* the part failed. | **Recommended for Phase 3** |
| **Strategy B: Multimodal Direct Vector Matching** | Citizen photo is embedded via CLIP/SigLIP ➔ searched directly against visual embeddings of reference images in Qdrant Named Vectors. | No LLM translation step needed. | Future enhancement (can run in parallel via Qdrant Named Vectors). |

---

## 5. Technical Specification: Payload & Endpoint Contract

### 5.1. AgriConnect ➔ Akvo RAG (`chat_url`)
AgriConnect calls the existing `chat_url` with multipart form data:

```python
# In backend/services/external_ai_service.py:
form_data = {
    "payload": json.dumps({
        "job": "chat",
        "prompt": prompt,
        "chats": [
            {
                "role": "user",
                "content": "Pump handle is stuck",
                "media": [{"type": "image", "filename": "broken_handle.jpg"}]
            }
        ],
        "callback_params": {
            "message_id": 1042,
            "customer_id": 55,
            "ticket_id": 312,
            "tenant_id": "unicef-water-kenya"
        }
    })
}
files = {"file": ("broken_handle.jpg", image_bytes, "image/jpeg")}

response = await client.post(self.token.chat_url, data=form_data, files=files, headers=headers)
```

### 5.2. Vision LLM Structured Prompt (Inside `vector-kb-mcp`)
```json
{
  "equipment_type": "Handpump",
  "detected_model": "Afridev",
  "component_identified": "Pump Handle & Fulcrum Pin Bracket",
  "visual_defect": "Fractured fulcrum bracket and displaced pivot bolt",
  "technical_search_intent": "Afridev handpump handle fulcrum pin replacement procedure bolt torque"
}
```

### 5.3. Callback Payload (Akvo RAG ➔ AgriConnect `/api/callback/ai`)
```json
{
  "job_id": "job-vision-88392",
  "status": "completed",
  "message_id": 1042,
  "customer_id": 55,
  "ticket_id": 312,
  "answer": "Based on your photo, the Afridev handpump handle bracket has a fracture on the fulcrum pin.\n\nRepair steps:\n1. Use a 17mm wrench to loosen the retaining bolts.\n2. Remove the handle and inspect bushing wear.\n3. Replace with a new fulcrum pin (Part #AF-04).",
  "media_references": [
    {
      "type": "diagram",
      "title": "Afridev Handle Assembly Diagram",
      "url": "https://storage.akvorag.org/kb-diagrams/unicef-water/afridev_manual_fig4.png"
    }
  ],
  "confidence_score": 0.92
}
```

---

## 6. Alignment with `akvo/akvo-rag` PR #163 Architecture

| Architecture Pillar (PR #163) | Integration Role in Image Recognition |
| :--- | :--- |
| **Monorepo Topology** | Lives inside the unified codebase alongside `backend`, `vector-kb-mcp`, and `frontend`. |
| **Redis RPC Queues** | Uses `MCPQueueDispatcher` for request-reply job dispatching (zero Celery overhead). |
| **Dual Workers** | Ingestion handled by `vector-kb-mcp-ingestion` (Docling parsing); runtime diagnostic queries handled by `vector-kb-mcp` (Vision + Vector retrieval). |
| **MinIO S3 Integration (:9010)** | Single authoritative store for both incoming citizen photos and Docling-extracted diagram schematics. |
| **PostgreSQL 17 (`asyncpg`)** | Stores job audit logs, multimodal prompt templates, and metadata indexes. |

---

## 7. Implementation Roadmap

1. **Phase 1: Ingestion Pipeline (Docling + MinIO)**
   - Implement figure and diagram cropping in `vector-kb-mcp-ingestion`.
   - Store cropped schematics in MinIO S3 and save reference metadata in Qdrant.
2. **Phase 2: Multipart Handling in Akvo RAG `chat_url`**
   - Extend the chat endpoint in Akvo RAG to accept optional file uploads and stage them to MinIO.
3. **Phase 3: Vision Recognition Tool in `vector-kb-mcp`**
   - Implement the `recognize_and_retrieve_manual` tool using OpenAI GPT-4o Vision structured output.
   - Wire tool output to Qdrant vector retrieval.
4. **Phase 4: End-to-End AgriConnect Verification**
   - Verify that citizen photos sent via WhatsApp trigger the entire pipeline and return diagnosis + diagram URLs via `/api/callback/ai`.
