# Exploration Note: Vector Database Evaluation — ChromaDB vs Qdrant for Akvo RAG

> **Status:** Draft / Exploration Note  
> **Context:** AkvoConnect Phase 3 (Multi-Tenancy, Multi-Sector, Multimodal Pump Diagnostics)  
> **Target System:** Akvo RAG & AgriConnect Integration  
> **Author:** Engineering Team  

---

## 1. Executive Summary

Currently, **Akvo RAG** relies on **ChromaDB** as the vector database for storing and querying Knowledge Base documents within AgriConnect (Phase 1 & 2).

As **Phase 3** begins, AkvoConnect is expanding into new domains (**Water/WASH** and **Public Health**), hosting multiple partners on shared infrastructure (**Multi-Tenancy**), and introducing image-based diagnostics (**Photo-based pump diagnostics**).

This document outlines the architectural analysis of why **Qdrant** is proposed to replace or upgrade ChromaDB, and demonstrates how Qdrant provides the foundational capabilities needed for multimodal document retrieval in Akvo RAG.

---

## 2. Current Pain Points & Architectural Drivers

1. **Multi-Tenancy Scalability:**
   - In ChromaDB, data isolation between tenants typically requires creating a separate collection per tenant or relying on standard metadata filtering.
   - Managing dozens or hundreds of collections in ChromaDB introduces significant memory overhead because each collection maintains its own distinct HNSW index.
2. **Single-Vector & Multimodal Limitations:**
   - ChromaDB primarily associates each record/point with a single embedding vector.
   - Phase 3 requires technical documents (e.g., UNICEF pump Operation & Maintenance manuals) to be retrievable both via **farmer/citizen text queries** and **photos of damaged spare parts**.
3. **Resource Efficiency & Production Footprint:**
   - ChromaDB is implemented primarily in Python (with C++ index bindings), resulting in a relatively high baseline RAM footprint and potential stability bottlenecks under high concurrent WhatsApp webhook traffic.

---

## 3. Deep Comparison: ChromaDB vs Qdrant

| Evaluation Criteria | ChromaDB (Current State) | Qdrant (Target Architecture) | Relevance to AkvoConnect Phase 3 |
| :--- | :--- | :--- | :--- |
| **Core Architecture** | Python (with C++ bindings) | Pure **Rust** | High CPU/RAM efficiency, deterministic memory usage, massive concurrency. |
| **Multi-Tenant Isolation** | Separate collection (RAM overhead) or slow metadata filters | **Payload-based Partitioning** + Indexed Payload Fields | Guarantees *Zero Cross-Tenant Leakage* at the vector index level for 8+ new partners. |
| **Multimodal Support** | Single vector per point | **Named Vectors (Multi-Vector per Point)** | A single document can store text vectors (`text-dense`), visual vectors (`image-clip`), and keyword vectors (`bm25-sparse`). |
| **Memory Optimization** | Limited | **Scalar & Product Quantization**, On-disk storage (mmap) | Reduces server cloud/Docker RAM footprint by up to 70%. |
| **Hybrid Search** | Limited / requires external pipeline | Native Dense + Sparse Vector Search | Enables accurate retrieval combining semantic meaning with exact spare part serial numbers. |
| **Operations & Observability** | Minimal / third-party tools | **Built-in Web UI Dashboard (Port 6333)** | Facilitates point inspection, metadata debugging, and snapshot backups for dev/data teams. |

---

## 4. Specific Qdrant Capabilities for AkvoConnect Phase 3

### 4.1. Payload-Based Multi-Tenancy Partitioning
Instead of provisioning separate collections for each partner, Qdrant allows all Knowledge Base documents to reside in a shared, partitioned collection with strict isolation guarantees:
- Dedicated payload indexes are created on `tenant_id` and `sector`.
- Query execution automatically scopes vector scans strictly to the matching tenant segment:
  ```json
  {
    "filter": {
      "must": [
        { "key": "tenant_id", "match": { "value": "unicef-water-kenya" } },
        { "key": "sector", "match": { "value": "water" } }
      ]
    }
  }
  ```

### 4.2. Named Vectors for Photo-Based Diagnostics
Qdrant natively supports storing multiple vector embeddings within a single manual record:
```json
{
  "id": "doc-manual-unicef-afridev-pg14",
  "vectors": {
    "text_embedding": [0.012, -0.043, 0.521, "..."],    // For text-based queries via WhatsApp
    "image_embedding": [0.091, 0.214, -0.118, "..."],   // For visual similarity matching of pump photos
    "bm25_sparse": { "indices": [102, 458], "values": [0.8, 0.3] } // For part numbers & serials
  },
  "payload": {
    "tenant_id": "unicef-water",
    "manual_title": "Afridev Handpump O&M Guide",
    "component": "Handle Pivot Pin",
    "diagram_image_url": "https://storage.akvoconnect.org/manuals/diagram_pin_01.png",
    "repair_instructions": "1. Inspect pivot pin wear. 2. Replace with M12 bolt..."
  }
}
```

---

## 5. Migration Considerations & Risk Mitigation

| Risk / Challenge | Severity | Mitigation Strategy |
| :--- | :---: | :--- |
| **Akvo RAG Interface Changes** | Medium | Introduce an adapter/repository abstraction within Akvo RAG so consumers are decoupled from Qdrant-specific SDK calls. |
| **Existing Data Migration** | Low | Implement a one-off batch migration script that reads existing ChromaDB collections and upserts points into Qdrant stamped with `tenant_id = "agri-kenya"`. |
| **Infrastructure Overhead** | Low | Qdrant runs as a lightweight official Docker container (`qdrant/qdrant:latest`) integrated directly into the `docker-compose.yml` stack. |

---

## 6. Conclusion & Recommended Next Steps

1. **ChromaDB** served its purpose well during initial validation (Phase 1 & 2: single tenant, single agriculture domain, text-only).
2. **Qdrant** is an architectural necessity for **Phase 3** to empower Akvo RAG to:
   - Handle multi-tenant isolation safely and cost-effectively.
   - Enable multimodal search (text and images) required for the UNICEF water pump diagnostic feature.
3. **Next Steps:**
   - Deploy a local Qdrant container for prototyping.
   - Benchmark Named Vectors (Text + Image Embeddings) using sample UNICEF handpump O&M manuals.
