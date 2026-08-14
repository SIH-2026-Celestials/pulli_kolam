# PULLI presentation Script (SIH / Hackathon Pitch)

**Total Duration**: ~5–7 Minutes  
**Focus**: The unique intersection of Indian heritage, advanced graph theory, custom machine learning, and production-grade system design.

---

## 1. The Hook & Problem (Duration: 1.5 Min)
> **Presenter 1:**
> "Good morning, respected judges. Today, we invite you to look at a centuries-old South Indian tradition through the lens of modern mathematics and artificial intelligence. 
> 
> This is **PULLI**—the first intelligent platform dedicated to the generation, analysis, and verification of **Pulli Kolam** patterns.
> 
> For generations, Kolams have been drawn on thresholds using a grid of dots, connected by a single, continuous, looping line. But beneath this beautiful art lies complex mathematics: graph theory, Eulerian loops, and dihedral symmetry groups.
> 
> Historically, digitizing, generating, and recognizing these patterns has been extremely difficult:
> 1. Traditional computer vision fails to detect hand-drawn dot grids under rotation, perspective skew, or poor lighting.
> 2. Traditional generative systems produce broken lines, disconnected components, and repetitive patterns that violate the fundamental rules of valid Kolams.
> 
> PULLI solves this by bridging the gap between artistic expression and rigorous computer science."

---

## 2. Technical Architecture & AI Models (Duration: 2 Min)
> **Presenter 2:**
> "To achieve this, we built a two-stage hybrid AI architecture that completely separates image detection from structural generation.
> 
> First, our **AI Recognition Layer (M4.2)**:
> * Instead of classical heuristics, we developed a **Gated Dot-Lattice Detector**. It uses a convolutional neural network (CNN) to predict dot heatmaps with sub-pixel precision.
> * We implemented a custom **geometric deskewing algorithm** that calculates the perspective transform of skewed camera images, allowing the system to accurately detect dot lattices in real-world photos.
> 
> Second, our **Generative Layer (M5)**:
> * PULLI does not use simple random generation or standard LLMs, which cannot guarantee mathematical correctness.
> * Instead, the **M5 Placement Scorer** uses a deep Multi-Layer Perceptron (MLP) trained on over half a million structural distribution steps. It guides a **multi-restart search algorithm** to build paths dot-by-dot.
> * A strict **mathematical gate** inspects the generated graphs in real-time, verifying that the pattern forms a single connected component and an **Eulerian circuit** (a single continuous loop)."

---

## 3. Production Hardening & System Design (Duration: 1.5 Min)
> **Presenter 1:**
> "We didn't just build research notebooks. We built a hardened, production-grade cloud architecture:
> 
> 1. **Unified Storage Abstraction**: We implemented a storage layer that writes to local disk in development but seamlessly switches to **Cloudflare R2 Object Storage** in production to serve SVGs and PNGs via pre-signed secure URLs.
> 2. **Multi-Metadata Schema & Alembic**: The user session database and the core model records are merged into a single connection pool. Database migrations are fully automated using **Alembic**, running automatically on startup.
> 3. **Production Dockerization**: The backend is packaged into a slim, non-root Docker container utilizing PyTorch (CPU-only version) to keep the footprint small and cost-effective. It dynamically binds to platform ports for deployment on **Render**.
> 4. **Strict Security Policies**: The API features strict, non-wildcard CORS origin checks and session cookies flagged with `HttpOnly`, `Secure`, and `SameSite=Lax` to prevent cross-site scripting (XSS) and forgery."

---

## 4. Key Metrics & Impact (Duration: 1 Min)
> **Presenter 2:**
> "Here are our verified benchmark results:
> * **100% Topological Uniqueness**: The M5 scorer generates 100% unique Kolams; there are zero duplicate structures.
> * **Reliability-at-K**: Our guided search achieves an **82% validity rate** on the first attempt, and a **100% success rate** within 10 search attempts.
> * **Continuous Integration**: The entire codebase is backed by **75 unit and integration tests** running automatically in our GitHub Actions CI pipeline.
> * **Response Latency**: Generation and mathematical analysis execute in under 20 seconds on standard CPU cores, requiring no expensive GPU instances.
> 
> In conclusion, PULLI preserves a rich cultural heritage by formalizing its mathematical foundation, making Indian heritage accessible, verifiable, and generative for the modern digital era.
> 
> Thank you, we are now open to your questions."

---

## 💡 Pro-Tips for Q&A:
* **How does it handle GPUs?** Explain that we intentionally optimized the models to run on CPU to avoid hosting costs, making it cheap and scalable to deploy.
* **Why not use LLMs (like GPT-4) to generate Kolams?** LLMs are token-based and fail at spatial/graph reasoning. They cannot guarantee that a line will form a mathematically valid closed loop. PULLI guarantees loop validity using Eulerian graph checks.
* **How are images stored?** Explain that they are stored as raw SVGs and PNGs in Cloudflare R2 object storage, completely separating file storage from metadata in PostgreSQL.
