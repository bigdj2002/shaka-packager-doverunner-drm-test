# DoveRunner DRM Packaging POC: Shaka Packager Migration

**Version:** 1.0 (Draft)
**Date:** January 2026
**Status:** Proof of Concept

---

## 1. Executive Summary

This document outlines a Proof of Concept (POC) for migrating video packaging operations from AWS MediaConvert to an in-house solution based on Shaka Packager. The initiative aims to reduce operational costs, increase control over the packaging pipeline, and enable future extensibility for custom DRM workflows and advanced features.

**Key Objectives:**
- Replace MediaConvert packaging functionality while maintaining output quality and compatibility
- Reduce AWS service costs by 60-80% for packaging operations
- Establish foundation for custom DRM integration and advanced packaging features
- Maintain support for existing playback platforms (iOS/FairPlay, Android/Widevine, Web/DASH)

---

## 2. Problem Statement & Motivation

### 2.1 Current Challenges

**Cost Concerns:**
- MediaConvert pricing is based on output duration and resolution (per-minute billing)
- High-volume processing incurs significant monthly costs ($X,XXX+ estimated)
- Limited cost optimization options within MediaConvert service boundaries

**Flexibility Limitations:**
- Vendor lock-in to AWS MediaConvert feature set and release cycles
- Limited customization of packaging workflows (e.g., custom manifest manipulation)
- Dependency on AWS SPEKE for DRM key management with limited flexibility

**Operational Constraints:**
- Black-box service with limited visibility into packaging internals
- Debugging and troubleshooting requires AWS support engagement
- Cannot easily integrate custom pre/post-processing steps

### 2.2 What We Aim to Solve

1. **Cost Reduction:** Eliminate per-minute MediaConvert charges by using self-hosted packaging
2. **Custom DRM Integration:** Direct CPIX integration with DoveRunner KMS without SPEKE intermediary
3. **Workflow Control:** Full control over manifest generation, segment naming, and output structure
4. **Debugging Capability:** Direct access to packaging logs and intermediate outputs
5. **Feature Velocity:** Ability to implement custom features (e.g., absolute manifest URLs, custom metadata injection)

---

## 3. Current State: MediaConvert Output Overview

### 3.1 Output Group Summary

**HEVC-4K Output Groups:**

| Output Group              | Type                   | Container | DRM/Encryption  | Manifests     | Segment Length |
|---------------------------|------------------------|-----------|-----------------|---------------|----------------|
| HEVC_CMAF_4K_CLEAR_SDR    | CMAF_GROUP_SETTINGS    | CMFC      | None (CLEAR)    | HLS + DASH    | 6s             |
| HEVC_CMAF_4K_DRM_SDR      | CMAF_GROUP_SETTINGS    | CMFC      | SPEKE/SAMPLE_AES| HLS + DASH    | 6s             |
| HEVC_DASH_4K_DRM_SDR      | DASH_ISO_GROUP_SETTINGS| fMP4      | SPEKE/CENC      | DASH          | 6s             |

**AVC-FHD Output Groups:**

| Output Group              | Type                   | Container | DRM/Encryption  | Manifests     | Segment Length |
|---------------------------|------------------------|-----------|-----------------|---------------|----------------|
| AVC_HLS_FHD_CLEAR_SDR     | HLS_GROUP_SETTINGS     | TS        | None (CLEAR)    | HLS           | 6s             |
| AVC_HLS_FHD_DRM_SDR       | HLS_GROUP_SETTINGS     | TS        | SPEKE/SAMPLE_AES| HLS           | 6s             |
| AVC_DASH_FHD_DRM_SDR      | DASH_ISO_GROUP_SETTINGS| fMP4      | SPEKE/CENC      | DASH          | 6s             |

### 3.2 Track Inventory

**Video Renditions:**
- HEVC: 6 renditions (3840p, 2560p, 1920p, 1280p, 854p, 640p)
- AVC: 6 renditions (1920p, 1280p, 960p, 854p, 640p, 384p)

**Audio Tracks:**
- Stereo AAC 128kbps (Korean language)

**DRM Systems:**
- FairPlay (Apple/iOS) via SAMPLE_AES encryption (TS containers)
- Widevine (Android/Web) via CENC encryption (fMP4 containers)
- CBCS scheme support for FairPlay (CMAF)

---

## 4. Proposed Solution: Shaka Packager In-House

### 4.1 Architecture Overview

```
┌──────────────────┐
│ Encoded MP4 Files│ (from MediaConvert encoding stage)
│ (HEVC/AVC)       │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│   DoveRunner Integration Script              │
│   (doverunner-integration-script.py)         │
│   • CPIX API client integration              │
│   • Key/IV management                        │
│   • Profile selection (HEVC/AVC)             │
└────────┬─────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│   Shaka Packager (v3.2.0+)                   │
│   • Multi-DRM encryption (FairPlay/Widevine) │
│   • HLS (TS/CMAF) + DASH (fMP4) packaging    │
│   • Segment generation (6s duration)         │
└────────┬─────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│   Post-Processing                            │
│   • Manifest URL rewriting (absolute paths)  │
│   • FairPlay IV injection                    │
│   • Command logging                          │
└────────┬─────────────────────────────────────┘
         │
         ▼
┌──────────────────┐
│ Output Manifests │ (master.m3u8, stream.mpd)
│ & Segments       │ (.ts, .m4s, .cmfv, .cmfa)
└──────────────────┘
```

### 4.2 Technology Stack

- **Packaging Engine:** Shaka Packager v3.2.0 (open-source, Google-maintained)
- **DRM Key Management:** DoveRunner CPIX API (direct integration)
- **Orchestration:** Python 3.x wrapper scripts
- **Infrastructure:** Compute instances (EC2/on-prem) with sufficient CPU/disk
- **Storage:** S3-compatible storage for output artifacts

---

## 5. Cost Analysis (Condensed)

- **MediaConvert (current):** Per-minute pricing; high spend at 10k vids/month (3min avg), 50% HEVC 4K, 50% AVC FHD, all DRM.
- **Shaka Packager (target):** Self-managed compute + storage + transfer (e.g., 2× c5.2xlarge class).
- **Savings:** ~63% vs MediaConvert (encoding/packaging bill).
- **Duplicate encodes:** Today HEVC/AVC ladders run ~3× (5× for low-FPS). Collapsing to 1× cuts the **encoding portion** by roughly ~67% (3→1) or ~80% (5→1).
- **Effort:** Initial 4–6 weeks; maintenance 1–2 days/month. Break-even in ~2–3 months.

---

## 6. Feature Compatibility & Gap Analysis

### 6.1 Supported Features ✅

| Feature                                  | MediaConvert | Shaka Packager | Status |
|------------------------------------------|--------------|----------------|--------|
| HLS TS packaging (AVC)                   | ✅           | ✅             | ✅ POC Complete |
| DASH fMP4 packaging (AVC/HEVC/AV1)       | ✅           | ✅             | ⚠️ AV1 not yet validated in POC |
| CMAF packaging (HEVC/AV1)                | ✅           | ✅             | ⚠️ AV1 not yet validated in POC |
| FairPlay DRM (SAMPLE_AES)                | ✅           | ✅             | ✅ POC Complete |
| Widevine DRM (CENC/CBCS)                 | ✅           | ✅             | ✅ POC Complete |
| Multi-bitrate ABR ladders                | ✅           | ✅             | ✅ POC Complete |
| 6-second segment duration                | ✅           | ✅             | ✅ Configurable |
| Custom key/IV via CPIX                   | ⚠️ (SPEKE)   | ✅             | ✅ Direct integration |

### 6.2 Identified Gaps & Limitations ⚠️

#### 6.2.1 **HLS Discontinuity Tags**

**Issue:** Shaka Packager inserts `#EXT-X-DISCONTINUITY` before `#EXT-X-KEY` in encrypted HLS streams, which is technically valid but may cause playback issues on certain legacy players.

**Impact:** Low (most modern players handle this correctly)

**Mitigation:** Post-processing script to remove discontinuity tags for fully encrypted VOD content

**Development Effort:** 1-2 days

#### 6.2.2 **SPEKE Integration (if needed for backwards compatibility)**

**Issue:** Shaka Packager does not natively support AWS SPEKE protocol for key retrieval.

**Impact:** Medium (blocks migration if SPEKE is required)

**Mitigation:**
- Option 1: Continue direct CPIX integration with DoveRunner KMS (preferred)
- Option 2: Build SPEKE-to-CPIX adapter layer

**Development Effort:**
- Option 1: None (already implemented)
- Option 2: 2-3 weeks

#### 6.2.3 **Live Streaming / Low-Latency Support**

**Issue:** Current POC focuses on VOD. Live streaming requires additional workflow changes.

**Impact:** High (if live streaming is required)

**Mitigation:**
- Shaka Packager supports live streaming with `--segment_template` and time-based segments
- Requires workflow changes for continuous input and manifest updates

**Development Effort:** 4-6 weeks for live streaming pipeline

#### 6.2.4 **Closed Captions / Subtitles**

**Issue:** Subtitle packaging (WebVTT, TTML) tested but not extensively validated in POC.

**Impact:** Medium (if subtitles are critical)

**Mitigation:** Extended testing with sample subtitle files

**Development Effort:** 1 week for validation

#### 6.2.5 **HDR / Dolby Vision Metadata Passthrough**

**Issue:** Advanced HDR metadata (Dolby Vision, HDR10+) passthrough not tested.

**Impact:** Low (if HDR content is not immediate priority)

**Mitigation:** Shaka Packager supports HDR metadata; requires testing with HDR source files

**Development Effort:** 1-2 weeks

#### 6.2.6 **AV1 Validation & Device Support**

**Issue:** AV1 packaging is supported by Shaka Packager (DASH/CMAF fMP4), but not validated in this POC; HLS fMP4 AV1 has limited device support and FairPlay AV1 is not available.

**Impact:** Medium (may affect iOS/macOS playback and legacy devices)

**Mitigation:** Limit AV1 to DASH/CMAF targets initially; add device compatibility matrix and fallback ladders (AVC/HEVC).

**Development Effort:** 1-2 weeks for packaging tests + playback/device validation

#### 6.2.7 **Poster/Thumbnail Generation**

**Issue:** Shaka Packager is packaging-only and does not generate poster or thumbnail images (MediaConvert handled this).

**Impact:** Medium (affects delivery of static preview assets)

**Mitigation:** Keep a separate thumbnail/poster workflow (e.g., MediaConvert/FFmpeg job) alongside Shaka packaging.

**Development Effort:** 1-2 days to wire a parallel image-extract step

### 6.3 Feature Checklist (POC Validation)

| Feature                                  | Status | Notes                                      |
|------------------------------------------|--------|--------------------------------------------|
| AVC H.264 packaging (HLS TS)             | ✅     | FairPlay DRM tested                        |
| AVC H.264 packaging (DASH fMP4)          | ✅     | Widevine DRM tested                        |
| HEVC H.265 packaging (CMAF)              | ✅     | FairPlay + Widevine dual-DRM tested        |
| HEVC H.265 packaging (DASH fMP4)         | ✅     | Widevine DRM tested                        |
| Multi-bitrate ABR (6 video renditions)   | ✅     | AVC & HEVC ladders validated               |
| Audio-only tracks (AAC stereo)           | ✅     | Korean language track tested               |
| 6-second segment duration                | ✅     | Configurable via `--segment_duration`      |
| FairPlay key/IV injection                | ✅     | CPIX integration + custom IV handling      |
| Widevine PSSH generation                 | ✅     | CPIX integration with multi-key support    |
| CENC encryption scheme                   | ✅     | Default for Widevine/DASH                  |
| CBCS encryption scheme                   | ✅     | FairPlay/CMAF tested                       |
| Absolute URL manifest rewriting          | ✅     | Post-processing for CDN deployment         |
| Command logging & debugging              | ✅     | Per-script log files implemented           |
| Clear (non-DRM) packaging                | ✅     | Verified for QA/testing purposes           |

---

## 7. Technical Limitations & Shaka Packager Constraints

### 7.1 Known Shaka Packager Limitations

1. **No Built-in SPEKE Support**
   - Requires custom key management integration (CPIX, raw keys, etc.)
   - **Our Solution:** Direct CPIX API integration with DoveRunner KMS

2. **Limited Live Streaming Features**
   - Basic live streaming support exists but lacks LL-HLS/LL-DASH optimizations
   - **Impact:** Not an issue for current VOD-focused use case

3. **Manifest Customization**
   - Some advanced manifest directives require post-processing
   - **Our Solution:** Python post-processing scripts for URL rewriting and metadata injection

4. **Error Handling**
   - CLI-based tool with exit codes; requires wrapper logic for robust error handling
   - **Our Solution:** Python wrapper with retry logic and detailed logging

5. **Performance Tuning**
   - Single-process execution per job; parallelization must be handled externally
   - **Our Solution:** Job queue with multiple workers (future roadmap)

### 7.2 What is NOT Supported (Currently)

| Feature                                      | Feasibility | Notes                                           |
|----------------------------------------------|--------------|-------------------------------------------------|
| Real-time transcoding (encoding + packaging) | 🔴           | Shaka Packager is packaging-only; requires FFmpeg or MediaConvert for encoding |
| DRM license server                           | 🔴           | Separate component; DoveRunner KMS handles this |
| Content-aware encoding (QVBR, ML-based)      | 🔴           | MediaConvert feature; not applicable to packaging |
| Automated QA/QC (audio silence detection)    | 🔴           | Requires additional tooling (e.g., FFmpeg analysis) |
| AWS-specific integrations (S3 events, etc.)  | ⚠️           | Requires custom Lambda/event-driven architecture |

---

## 8. Security Considerations

### 8.1 Key Management

**Current MediaConvert Approach:**
- AWS SPEKE protocol with KMS integration
- Keys retrieved per-job with short TTL
- AWS IAM-based access control

**Shaka Packager Approach:**
- Direct CPIX API calls to DoveRunner KMS
- Keys retrieved with authentication token
- Keys passed to Shaka Packager via CLI arguments (short-lived process)

**Security Enhancements:**
- ✅ Keys never persisted to disk (CLI arguments only)
- ✅ CPIX API uses HTTPS with token-based authentication
- ✅ Command logs redact sensitive key material
- ⚠️ Requires secure compute environment (encrypted EBS, IAM roles)

### 8.2 Access Control

| Component                  | Access Control Mechanism                      |
|----------------------------|-----------------------------------------------|
| DoveRunner CPIX API        | Bearer token authentication (short-lived)     |
| Shaka Packager execution   | IAM role on EC2 instance (no hardcoded creds) |
| Output storage (S3)        | Bucket policies + IAM roles                   |
| CDN distribution           | Existing signed URL / token-based auth        |

### 8.3 Compliance & Auditing

- **Audit Logging:** All packaging jobs logged with content ID, DRM parameters, and output paths
- **Key Rotation:** Supported via CPIX API (per-content unique keys)
- **DRM Compliance:** FairPlay and Widevine robustness rules enforced by player SDKs (not packaging layer)

### 8.4 Risks & Mitigation

| Risk                                       | Likelihood | Impact | Mitigation                                      |
|--------------------------------------------|------------|--------|-------------------------------------------------|
| Key exposure in process memory             | Low        | High   | Short-lived processes; secure compute environment |
| CPIX API token compromise                  | Low        | High   | Token rotation policy; rate limiting            |
| Manifest tampering (CDN)                   | Medium     | Medium | Signed URLs; manifest integrity checks          |
| Compute instance compromise                | Low        | High   | OS hardening; network segmentation; IAM least-privilege |

---

## 9. High-Level Workflow

### 9.1 End-to-End Processing Flow

```
STEP 1: Content Ingestion & Encoding
  • Source file uploaded to S3
  • MediaConvert encoding job (HEVC/AVC renditions)
  • Output: Mezzanine MP4 files (per-resolution)

↓

STEP 2: DRM Key Provisioning
  • Python script calls DoveRunner CPIX API
  • Input: content_id, enc_token, DRM type (FairPlay/Widevine)
  • Output: Encryption keys (KID, KEY, IV, PSSH)

↓

STEP 3: Shaka Packager Execution
  • Input: Mezzanine MP4 files + DRM keys
  • Process: Segmentation (6s) + encryption + manifest generation
  • Output: HLS/DASH manifests + encrypted segments

↓

STEP 4: Post-Processing
  • Manifest URL rewriting (relative → absolute or CDN URLs)
  • FairPlay IV injection (HLS playlists)
  • Validation checks (segment count, encryption headers)

↓

STEP 5: Distribution
  • Upload manifests + segments to S3 (or CDN origin)
  • Trigger CDN cache warming (optional)
  • Notify downstream systems (catalog update)
```

### 9.2 Job Execution Model

**Option A: Synchronous (Current POC)**
- Shell scripts invoked per-job via cron, Lambda, or orchestrator
- Blocking execution; suitable for low-volume or on-demand processing

**Option B: Asynchronous (Production Recommendation)**
- Job queue (SQS, RabbitMQ) with worker pool
- Parallel processing with concurrency controls
- Retry logic and dead-letter queue for failed jobs

---

## 10. Scalability & Extensibility

### 10.1 Scalability Advantages

**Horizontal Scaling:**
- Add more compute instances to increase throughput
- Linear cost scaling (vs. MediaConvert's per-minute pricing)
- Auto-scaling based on queue depth

**Performance Optimization:**
- In-memory processing (tmpfs for segments)
- Parallel job execution across workers
- CDN-aware output path optimization

**Cost Efficiency at Scale:**
- Reserved instance pricing for predictable workloads
- Spot instances for batch processing (60-70% discount)
- No MediaConvert rate limits or throttling

### 10.2 Extensibility & Custom Features

**Already Implemented:**
- ✅ Absolute URL manifest generation (not possible in MediaConvert)
- ✅ Custom IV handling for FairPlay (workaround for Shaka Packager limitation)
- ✅ Flexible output directory structure

**Future Roadmap (Enabled by In-House Solution):**

1. **Advanced Manifest Manipulation**
   - Custom `#EXT-X-PROGRAM-DATE-TIME` insertion for live-to-VOD
   - Server-side ad insertion (SSAI) marker injection
   - Multi-CDN failover URLs

2. **Multi-DRM Single-Package**
   - Single CMAF output playable on both iOS (FairPlay) and Android (Widevine)
   - Reduces storage by 30-40% vs. separate packages

3. **Dynamic Packaging**
   - Just-in-time packaging from mezzanine files
   - Reduces storage for long-tail content

4. **Advanced Analytics**
   - Segment-level quality metrics (VMAF, PSNR)
   - Packaging performance benchmarks
   - DRM handshake success rate tracking

5. **Custom Encryption Schemes**
   - Alternative DRM systems (e.g., internal token-based protection)
   - Hybrid encryption for freemium content

6. **Localization & Personalization**
   - Region-specific manifest generation (CDN edge optimization)
   - User-tier-based rendition filtering

---

## 11. Development Resource Requirements

### 11.1 Initial POC (Completed)

- **Duration:** 4 weeks
- **Effort:** 1 engineer (full-time)
- **Deliverables:**
  - Python wrapper scripts
  - CPIX integration
  - Packaging scripts for AVC/HEVC
  - Basic testing & validation

### 11.2 Production Readiness (Estimated)

| Phase                        | Duration  | Engineer | Key Activities                                    |
|------------------------------|-----------|----------|---------------------------------------------------|
| Feature Completion           | 2 weeks   | 1 FTE    | Discontinuity tag removal, subtitle support       |
| Infrastructure Setup         | 2 weeks   | 1 DevOps | EC2 provisioning, job queue, monitoring           |
| Integration & Testing        | 3 weeks   | 1 FTE    | End-to-end workflow, load testing, QA             |
| Documentation & Handoff      | 1 week    | 1 FTE    | Runbooks, troubleshooting guides, training        |
| **Total**                    | **8 weeks** | **1-2 FTE** | From POC to production deployment             |

### 11.3 Ongoing Maintenance

- **Monthly Effort:** 1-2 days/month
- **Activities:**
  - Shaka Packager version updates
  - Bug fixes and script enhancements
  - Performance tuning

---

## 12. Risks & Mitigation Strategies

| Risk                                  | Impact | Mitigation                                                                 |
|---------------------------------------|--------|---------------------------------------------------------------------------|
| Shaka Packager stability issues       | High   | Extensive testing; community support; fallback to MediaConvert if critical |
| DRM compatibility issues (players)    | High   | Validation with all target platforms; beta testing with real users         |
| Performance bottlenecks at scale      | Medium | Load testing; horizontal scaling; queue-based architecture                 |
| Key management security incident      | High   | Least-privilege IAM; audit logging; incident response plan                 |
| Operational complexity (vs. managed)  | Medium | Comprehensive monitoring; alerting; runbooks; on-call rotation             |

---

## 13. Recommendations & Next Steps

### 13.1 Recommendation: Proceed with Production Deployment

**Rationale:**
- ✅ POC successfully validates core functionality (AVC/HEVC, FairPlay/Widevine)
- ✅ Significant cost savings (63% reduction)
- ✅ Technical gaps are addressable with reasonable development effort
- ✅ Security model is sound with proper controls
- ✅ Extensibility enables future feature development

**Conditions:**
- Complete identified gaps (discontinuity tag handling, subtitle validation)
- Implement production-grade infrastructure (job queue, monitoring)
- Conduct load testing with production-scale workloads
- Define rollback plan to MediaConvert if issues arise

### 13.2 Phased Rollout Plan

**Phase 1: Pilot (Month 1-2)**
- Deploy for 10% of new content (low-risk catalog)
- Monitor playback metrics closely
- Gather operational learnings

**Phase 2: Expansion (Month 3-4)**
- Increase to 50% of new content
- Optimize based on pilot feedback
- Finalize runbooks and training

**Phase 3: Full Migration (Month 5-6)**
- Migrate 100% of new content to Shaka Packager
- Maintain MediaConvert as fallback for 90 days
- Decommission MediaConvert packaging workflows

### 13.3 Success Criteria

| Metric                          | Target                     | Measurement Method                |
|---------------------------------|----------------------------|-----------------------------------|
| Cost Reduction                  | ≥60% vs. MediaConvert      | Monthly AWS bill comparison       |
| Playback Success Rate           | ≥99.5% (same as current)   | CDN analytics + player telemetry  |
| Packaging Job Success Rate      | ≥99% (excluding input errors) | Job queue metrics              |
| Mean Time to Package (per video)| ≤10 minutes                | Workflow telemetry                |
| Security Incidents              | 0 (key exposure, DRM bypass) | Audit logs + security monitoring |

---

## 14. Appendices

### A. Glossary

- **ABR:** Adaptive Bitrate (streaming)
- **CMAF:** Common Media Application Format
- **CPIX:** Content Protection Information Exchange
- **CENC:** Common Encryption
- **CBCS:** Cipher Block Chaining Scheme
- **SAMPLE_AES:** Sample AES encryption (for HLS TS)
- **SPEKE:** Secure Packager and Encoder Key Exchange (AWS protocol)
- **KMS:** Key Management System

### B. References

- Shaka Packager GitHub: https://github.com/shaka-project/shaka-packager
- DoveRunner CPIX API Documentation: [internal link]
- MediaConvert Pricing: https://aws.amazon.com/mediaconvert/pricing/

### C. Contact & Review

- **Document Owner:** [Your Name]
- **Technical Review:** [Team Lead]
- **Business Review:** [Product Manager]
- **Last Updated:** January 2026

---

**END OF DOCUMENT**
