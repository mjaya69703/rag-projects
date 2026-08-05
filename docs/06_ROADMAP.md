# Roadmap

> **Status 06-08-2026:** Sprint 1-5 selesai (Sprint 5 = custom SPA, bukan Streamlit — lihat
> `docs/05_DEVELOPMENT_FLOW.md`). Sprint 6: artefak deployment siap di `deploy/`, deploy nyata
> (cloudflared, Access policy) menunggu akses user ke LXC & Cloudflare Dashboard.
> Backlog lain: auto top-k, slide-mode parser, model embedding alternatif, multi-user auth,
> export/import session (lihat `.agents/07_ROADMAP.md`).

## 📅 Timeline (Estimasi: 2-3 Minggu)

### Week 1: Core Development
| Hari | Fokus | Output |
|------|-------|--------|
| Day 1-2 | Sprint 1 (PDF Ingestion) | PDF parser & ChromaDB integration |
| Day 3-4 | Sprint 2 (Query & LLM) | RAG engine working |
| Day 5 | Sprint 3 (Semantic Cache) | Cache system active |

### Week 2: API & UI
| Hari | Fokus | Output |
|------|-------|--------|
| Day 6-7 | Sprint 4 (FastAPI) | REST API ready |
| Day 8-9 | Sprint 5 (Streamlit) | UI complete |
| Day 10 | Bug fixing & optimization | Stable version |

### Week 3: Deployment & Polish
| Hari | Fokus | Output |
|------|-------|--------|
| Day 11-12 | Sprint 6 (Deployment) | Live & accessible |
| Day 13-14 | Testing & documentation | Production ready |

## 🎯 Milestone

### M1: MVP (Minimum Viable Product) - End of Week 1
- Bisa upload PDF
- Bisa tanya jawab
- Basic UI (belum ada Cloudflare)

### M2: Beta Release - End of Week 2
- Full UI dengan Streamlit
- Semantic cache active
- API documented

### M3: Production Release - End of Week 3
- Deployed via Cloudflare Tunnel
- Secured with Cloudflare Access
- Auto-start service
- Documentation complete

## 📊 Key Performance Indicators (KPI)
- **Accuracy:** >80% jawaban relevan dengan dokumen
- **Latency:** <5 detik untuk respon pertama, <1 detik untuk cached
- **Token Efficiency:** >30% penghematan token berkat cache
- **Uptime:** 99% (auto-restart on failure)