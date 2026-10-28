# GLOSSARY.md — Beginner Terms

Plain-language definitions. Add new terms as you meet them (alphabetical within each section).

## AI & LLM basics

- **LLM (Large Language Model):** A model trained to predict the next piece of text. Given a prompt, it generates a continuation (an answer).
- **Parameters (e.g., "4B"):** The model's learned numbers. 4B = 4 billion. More parameters usually means smarter, but also slower and more RAM.
- **Quantization (Q4, Q8):** Storing the parameters with fewer bits so the model fits in less RAM and runs faster, with a small quality loss. (Relevant to local models; OpenAI handles this for us.)
- **Token:** A chunk of text the model reads or writes (≈ ¾ of an English word). Speed is measured in tokens/second.
- **Context window (`num_ctx`):** The maximum number of tokens the model can "see" at once: system prompt, history, retrieved chunks and the answer together.
- **Prompt / system prompt:** The text we send to the model. The *system* prompt sets the rules ("answer only from the context").
- **Temperature:** The randomness of the output. Low (0–0.2) = focused and repeatable, which is good for RAG and judging.
- **Inference:** Running a trained model to get an output. Our LLM inference happens on OpenAI's servers. Embeddings and reranking run locally on CPU.
- **Hallucination:** The model states something that sounds plausible but isn't supported by facts or the provided context.
- **Thinking / reasoning mode:** Some models write hidden "thoughts" before answering. Better on hard problems, but slower, and you pay for those hidden tokens.
- **Reasoning effort:** An OpenAI setting (`none`, `low`, `medium`, `high` …) that controls how much hidden reasoning a model does. We use `none` for the judge and `low` for the generator.
- **Structured output:** Forcing the model to reply in a fixed JSON shape (a schema) so code can read it reliably.
- **LLM-as-judge:** Using an LLM to evaluate something (Is this chunk relevant? Is this answer grounded?).
- **OpenAI API:** OpenAI's paid web service for its models. Our backend sends it messages over HTTPS and gets answers (streamed) back.
- **API key:** A secret password that identifies your account to an API, which then bills that account. Keep it in `.env`, never in code or git.
- **OpenAI project / budget limit:** A project groups keys and usage. A monthly budget limit stops spending at a set amount, as a safety net.
- **Input / output tokens & pricing:** You pay per token sent (input: prompt, history, chunks) and per token generated (output), priced per 1 million tokens. Output costs more.
- **Rate limit (HTTP 429):** The API refusing requests because you sent too many too fast, or ran out of credit. We retry with backoff.
- **Exponential backoff:** Waiting longer after each failed retry (1 s, 2 s, 4 s…) so you don't hammer a struggling service.
- **tiktoken:** OpenAI's tokenizer library. It counts tokens before sending, for cost estimates and to keep prompts under our cap.
- **Ollama:** A program for running open LLMs locally. It was considered for this project and replaced by the OpenAI API.

## RAG & retrieval

- **RAG (Retrieval-Augmented Generation):** First *retrieve* relevant pieces of your documents, then have the LLM *generate* an answer using them. The model answers from your data, not just its memory.
- **Agentic RAG:** RAG where the system makes decisions in a loop (route, judge relevance, rewrite the question, check the answer) instead of one fixed pass.
- **Ingestion:** Loading documents into the system: parse, split, embed, store.
- **Chunk / chunking:** Splitting a document into small passages (e.g., ~500 tokens). We retrieve chunks, not whole documents.
- **Chunk overlap:** Repeating a little text between neighbouring chunks so ideas cut at a boundary aren't lost.
- **Metadata / payload:** Extra info stored with each chunk (file name, page, section, repo path). Used for citations and filters.
- **Embedding:** A list of numbers (a vector) that represents the meaning of a text. Similar meanings give nearby vectors.
- **Dense vector:** An embedding where every position has a value (e.g., 384 numbers). Captures meaning.
- **Sparse vector:** A huge vector where almost every position is 0, with non-zero values only for the words present. Captures exact keywords.
- **Cosine similarity:** A score for how closely two vectors point in the same direction (1 = same meaning).
- **BM25:** A classic keyword-ranking formula (used by search engines) that rewards rare words matching the query.
- **Hybrid search:** Running dense (meaning) and sparse (keyword) search together and combining the results.
- **RRF (Reciprocal Rank Fusion):** Combines several ranked lists by giving each item `1/(k + rank)` points from each list. It is simple and robust.
- **Top-k:** Keep the best k results (e.g., top-20 candidates, then top-5 after reranking).
- **Bi-encoder:** Embeds the question and the chunk *separately*, then compares the vectors. Fast. This is how vector search works.
- **Cross-encoder / reranker:** Reads the question *and* the chunk together and outputs a relevance score. Accurate but slow, so we use it only on a short list.
- **Vector database:** A database built to store vectors and quickly find the nearest ones (Qdrant here).
- **Collection (Qdrant):** Like a table: a named set of points (vectors + payload).
- **Point (Qdrant):** One stored item: an ID, one or more vectors, and a payload.
- **IDF (Inverse Document Frequency):** A weight that makes rare words count more than common ones. "E-207" appears in few chunks, so a match on it is strong evidence; "the" appears everywhere, so it counts for almost nothing. Qdrant applies IDF to our `bm25` vectors.
- **Named vectors:** Several differently-shaped vectors stored on one Qdrant point (ours: `dense` and `bm25`), so one search can use either or both.
- **Payload index:** An index on a payload field (like `doc_id`), so filtering by it is fast instead of scanning every point.
- **Upsert:** "Update or insert": write a record, replacing it if one with the same ID already exists.
- **Deterministic ID (UUIDv5):** An ID computed from fixed inputs (document + chunk position), so the same chunk always gets the same ID. Re-running ingestion overwrites instead of duplicating.
- **Batching:** Processing items in groups (e.g. 32 chunks per model call, 256 points per Qdrant request) instead of one at a time (slow) or all at once (memory-hungry).
- **Contextual chunk header:** Text prepended *only for embedding* (e.g. `orbit_handbook.md > Installation > Wiring`), so a vector knows what a short chunk is about. The stored text stays unchanged.
- **Document registry:** Our Postgres table listing every indexed document with its fingerprint. It lets ingestion skip unchanged files and detect duplicates.
- **Retrieval funnel (wide-then-narrow):** A cheap search casts a wide net (10 candidates), then an expensive but accurate reranker picks the best 5. You get most of the reranker's accuracy at a fraction of its cost.
- **Latency/quality trade-off:** Reranking 20 candidates took ~1.7 s, 10 took ~0.9 s, with identical quality on our test set, so we chose 10. Decide such numbers by measuring, not guessing.
- **Grounding / grounded answer:** Every claim in the answer is supported by the retrieved chunks.
- **Citation:** A marker like `[2]` that links a sentence to the chunk it came from.
- **Query rewriting:** Rephrasing a question (adding keywords, removing ambiguity) to get better search results.
- **Routing:** Deciding which path a question takes (search the documents vs answer directly).
- **Golden dataset:** A hand-made list of questions with known correct answers and sources, used to measure quality.
- **hit@k:** The share of questions where the correct source appears in the top-k results.
- **MRR (Mean Reciprocal Rank):** The average of `1/rank` of the first correct result. Higher means the right answer appears nearer the top.
- **Section / heading path:** The chain of headings a chunk sits under, e.g. `Installation > Before you start`. It is stored with the chunk so answers can say *where* in a document something came from.
- **Token limit (of a model):** The most tokens a model can read at once. Our embedding model `bge-small` reads at most 512; anything longer is silently cut off. That's why chunks are capped at 400 of *our* tokens (different tokenizers count differently).
- **Tokenizer / encoding:** The rulebook that splits text into tokens. Different models use different ones, so "400 tokens" depends on who is counting. We count with tiktoken's `o200k_base`.
- **Recursive splitting:** Cutting text at the "nicest" boundary that fits: paragraph breaks first, then line breaks, then spaces, and only as a last resort mid-word.
- **Fingerprint (content hash):** A short code computed from content (SHA-256). Identical content always gives the identical fingerprint, so duplicates are easy to spot.
- **Deterministic:** Same input, same output, every time. Our chunking and sample files are deterministic, so fingerprints never change unless the content does.
- **Magic bytes / file signature:** The first few bytes that identify a real file type (`%PDF-` for PDF, `PK` for zip/DOCX). Extensions can lie; signatures rarely do.
- **Scanned PDF:** A PDF whose pages are photos of text. It has no text to extract without OCR (Optical Character Recognition), which we don't support, so it is reported clearly instead.
- **Normalisation:** Cleaning text without changing its meaning (unify line endings, remove junk control characters, collapse blank lines).
- **Encoding (text) / UTF-8 / Windows-1252 / BOM:** How characters are stored as bytes. UTF-8 is the modern standard. Windows-1252 is an older Windows one. A BOM is an invisible marker some editors put at the start of UTF-8 files; we strip it.
- **Prompt injection:** Text inside a document that tries to give the model instructions ("ignore previous rules…"). We treat document text as data, not instructions.

## Agents & memory

- **Agent:** A program where an LLM decides some of the next steps, rather than every step being fixed in code.
- **LangGraph:** A library for building agents as graphs of steps with shared state.
- **Graph / node / edge:** A node is a step (a Python function). An edge says what runs next. A *conditional edge* chooses the next node based on the state.
- **State:** The shared data the nodes read and update (question, retrieved chunks, answer, counters).
- **Reducer:** A rule for how a state field is updated (e.g., *append* new messages instead of replacing them).
- **Checkpointer / checkpoint:** A saved snapshot of the graph's state after each step, stored in Postgres. It is how memory survives restarts.
- **Thread / session:** One conversation. Its ID (`session_id` = LangGraph `thread_id`) selects which memory to load.
- **Conditional edge:** A graph edge that picks the next node by looking at the state (e.g. after grading: generate, rewrite, or give up).
- **Judge (in this project):** The small, cheap model making yes/no-style decisions (route, grade, rewrite, grounding check) with structured outputs, behind a `Judge` interface so tests can use a scripted fake.
- **Standalone question:** A follow-up like "what about its price?" rewritten so it makes sense alone ("what is the price of the Orbit T2?"). Search needs this.
- **Safe fallback:** What the agent does when a judge call fails: search rather than chat, keep passages rather than drop them, and say "couldn't verify" rather than "verified".
- **Checkpoint / thread_id:** After every agent step LangGraph saves a snapshot of the state in Postgres under a `thread_id` (our conversation id). The next message loads the latest snapshot, which is why memory survives restarts.
- **Deserialisation allow-list:** Only the listed Python types may be rebuilt from saved checkpoints, so a tampered database row can't make the app construct arbitrary objects.
- **Thread-to-async bridge:** The agent runs in one worker thread and hands events to the async web response through a queue, so the server stays responsive while it works.
- **409 Conflict:** The answer when a conversation is still busy with the previous message. Two simultaneous turns would corrupt its memory.
- **Loop guard:** A maximum count (e.g., 2 rewrites) that stops an agent looping forever.
- **Fallback:** A safe default used when something fails (e.g., the model returns invalid JSON).

## Backend & APIs

- **API:** A defined way for programs to talk to each other. Ours is HTTP + JSON.
- **Endpoint / route:** One URL + method the API offers, e.g., `POST /chat`.
- **FastAPI:** A Python framework for building APIs with automatic validation and docs at `/docs`.
- **Uvicorn:** The server program that runs the FastAPI app.
- **Pydantic model:** A Python class describing data shape + types. Invalid input is rejected automatically.
- **Async / await:** A way for one Python process to handle many waiting tasks (network calls, streams) without blocking.
- **Event loop:** The engine that runs async code. On Windows the default type has quirks with some database drivers.
- **Streaming:** Sending the response in pieces as it's produced, instead of all at the end.
- **SSE (Server-Sent Events):** A simple standard for streaming events from server to client over one HTTP connection.
- **Background task / job:** Work that continues after the HTTP response returns (e.g., ingesting a large repo). Its status is polled with a `job_id`.
- **Healthcheck — liveness vs readiness:** *Liveness* (`/health`) means "the process is running". *Readiness* (`/ready`) means "it can reach its dependencies and serve traffic".
- **Connection pool:** A set of reusable open database connections. It is faster than connecting on every request.
- **SQL / table / row / column:** SQL is the language for relational databases. Data lives in tables (like spreadsheets): each row is a record, each column a field.
- **Postgres schema (namespace):** A named folder of tables inside one database. Our tests create a throwaway schema so they never touch the real tables.
- **Transaction:** A group of database changes that succeed or fail together. `with pool.connection() as conn:` commits at the end of the block, or rolls everything back on error.
- **Query parameters (`%s`) / SQL injection:** Values are sent separately from the SQL text, so text like `'; DROP TABLE documents;--` in a file name is treated as data, never as a command. Pasting values into SQL strings is how SQL injection happens.
- **`ON CONFLICT ... DO UPDATE`:** Postgres's upsert: insert a row, or update it if the unique key (our `source`) already exists.
- **Consistency between two stores:** Qdrant and Postgres can't share one transaction, so we order the writes (chunks first, registry last). A crash in between is fixed by simply re-running.
- **Dependency injection / fakes:** The pipeline receives its embedder, store and registry instead of creating them, so tests can pass in-memory fakes and test the decision logic without Docker or models.
- **Idempotent:** Doing it twice has the same effect as doing it once (e.g., re-ingesting an unchanged file).
- **Content hash (SHA-256):** A fingerprint of a file's content. Same content gives the same hash, which lets us skip duplicates.
- **Environment variables / `.env`:** Settings given to a program from outside its code (URLs, model names, secrets). `.env` holds them locally and is never committed.
- **12-factor config:** The practice of keeping configuration in the environment, not in code.
- **App factory (`create_app`):** A function that builds and returns a fresh app. Tests can make an app with their own settings, and uvicorn calls it with `--factory`.
- **Lifespan:** Code that runs once when the API starts (open shared clients) and once when it stops (close them). It lives in `app/main.py`.
- **`SecretStr`:** A Pydantic type for secrets. It prints as `**********`, so keys and passwords don't leak into logs or error messages. Use `.get_secret_value()` only where the real value is needed.
- **Fail fast:** Detecting a problem (like an invalid setting) immediately at startup, with a clear error, instead of later in a confusing place.
- **`asyncio.gather`:** Runs several async tasks *at the same time* and waits for all of them. `/ready` checks 4 dependencies in parallel, so it takes about as long as the slowest one, not the sum of all four.
- **Timeout (`asyncio.wait_for`):** Gives up on a task after N seconds, so one stuck dependency can't hang the whole request.
- **Worker thread (`to_thread.run_sync`):** Runs blocking code (like a sync database driver) off the event loop, so the API stays responsive.

## Frontend (React, JavaScript)

- **Frontend / backend:** The frontend is what runs in the browser (our React app). The backend is the server (our Python API). They talk only over HTTP.
- **JavaScript (JS):** The programming language browsers run. React apps are written in it.
- **Node.js:** A program that runs JavaScript outside the browser. We need it for the frontend *tools* (Vite, tests, linting), not to run our backend.
- **npm / `package.json` / `package-lock.json`:** npm is JavaScript's package installer (like pip). `package.json` lists the dependencies and scripts. The lockfile records the exact version of every package so installs are reproducible. `npm ci` installs exactly what the lockfile says.
- **React:** A library for building UIs out of components. When data changes, React updates the screen for you.
- **Component:** A JavaScript function that returns UI (e.g., `<MessageBubble />`). Apps are trees of components.
- **JSX:** The HTML-like syntax inside JavaScript (`<div>{text}</div>`) that React uses to describe UI.
- **Props:** Inputs passed from a parent component to a child, like function arguments.
- **State (React):** Data a component remembers between renders (e.g., the messages list). Changing it re-renders the component.
- **Hook:** A special React function starting with `use` (`useState`, `useEffect`) that adds features to components. A *custom hook* (`useChatStream`) bundles related logic for reuse.
- **Effect (`useEffect`):** Code that runs after rendering to sync with the outside world (fetch data, start a timer). Its *cleanup* undoes it (abort the request).
- **`useReducer`:** A React hook that keeps related state (here: a conversation's turns while streaming) in one place, changed only through named actions like `token` or `done`. It is easier to follow and test than many separate `useState` calls.
- **StrictMode:** A development-only React check that runs some code twice to expose bugs such as impure state updates. This is why our state-update functions never have side effects.
- **Idle timeout (UI):** If the server sends nothing for 90 s (it normally pings every 15 s), the UI gives up with a clear message instead of spinning forever.
- **Re-render:** React calling a component function again to compute updated UI.
- **SPA (Single-Page Application):** One HTML page whose content is swapped by JavaScript, with no full page reloads.
- **Vite:** The frontend build tool. `npm run dev` gives a fast dev server. `npm run build` produces optimised static files in `dist/`.
- **Build / bundle:** Converting our source files (JSX, many modules) into a few optimised files browsers can load quickly.
- **Dev proxy:** A Vite setting that forwards `/api/...` requests from the dev server to the Python backend, so the browser sees one origin.
- **Origin / same-origin:** An origin is scheme + host + port (e.g., `http://localhost:8080`). The browser freely allows requests to the *same* origin.
- **CORS:** The browser's rules for calling a *different* origin. That origin must opt in. We avoid needing it by proxying `/api`.
- **Reverse proxy (nginx):** A server that receives requests and forwards them to another server. Our nginx serves the React files and forwards `/api` to FastAPI.
- **Proxy buffering:** A proxy collecting the whole response before sending it on. That breaks streaming, so we turn it off for `/api`.
- **`fetch`:** The browser's built-in function for HTTP requests.
- **ReadableStream / TextDecoder:** Let us read a response *piece by piece* as it arrives and turn the bytes into text. This is how we read streamed tokens.
- **EventSource:** The browser's built-in SSE client. It only supports GET, so we use `fetch` for our POST chat stream instead.
- **AbortController:** Cancels an in-flight `fetch`. It powers the Stop button and cleanup.
- **CSS Modules:** CSS files (`X.module.css`) whose class names are scoped to one component, so styles don't clash.
- **react-markdown:** Turns the model's Markdown answer into safe React elements, without injecting raw HTML.
- **XSS (Cross-Site Scripting):** An attack where untrusted text is run as code in the page. This is why we never inject model output as raw HTML.
- **ESLint / Prettier:** ESLint finds bugs and bad patterns in JS. Prettier formats code consistently. They're the frontend's equivalent of ruff.
- **Vitest / React Testing Library / jsdom:** Vitest runs JS tests. Testing Library renders components and finds things the way a user would ("the Send button"). jsdom is a fake browser for tests.
- **Accessibility (a11y) / `aria-live`:** Making the UI usable with keyboards and screen readers. `aria-live` announces new streamed text.

## Observability

- **Prompt caching (OpenAI):** When a new request starts with the same text as a recent one (e.g. our system prompt), OpenAI reuses its earlier work and bills those "cached" input tokens at a discount. Traces show it as `cache_read_input_tokens`.
- **Token budget (`PROMPT_MAX_TOKENS`):** Our own cap on prompt size. If the retrieved chunks don't fit, the least relevant ones are dropped, which bounds the cost of every request.
- **Inline citations `[n]`:** Numbers in the answer pointing at the numbered sources it used, so every claim can be checked.
- **Observability:** Being able to understand what the system did and why, from its outputs (logs, traces, metrics).
- **Structured logging:** Logs as key/value JSON (`{"event": "retrieved", "count": 5}`) instead of free text, so they're searchable.
- **Trace:** The full record of one request.
- **Span:** One timed step inside a trace (e.g., "rerank": 420 ms). Spans nest like a tree.
- **MLflow:** An open-source ML platform. We use its tracing UI (port 5000) to inspect every agent run.
- **Request ID:** A unique ID attached to every log line and trace for one request, so you can follow it end-to-end.
- **Latency:** How long something takes. **p95 latency** = 95% of requests are faster than this.

## DevOps & tooling

- **Virtual environment (venv):** A private folder of Python packages for one project, so projects don't conflict.
- **pip / requirements.txt:** The Python package installer, and the list of exact package versions to install.
- **Pinning:** Fixing exact versions (`fastapi==0.152.0`) so installs are reproducible.
- **Docker image:** A packaged, read-only template of an app and everything it needs.
- **Container:** A running instance of an image, isolated from your machine.
- **Docker Compose:** A YAML file plus a command that start several containers together as one system.
- **Volume:** Docker-managed storage that survives container restarts and rebuilds. Where our databases keep data.
- **Port mapping (`8000:8000`):** Exposes a container's port on your machine so you can open it at `localhost`.
- **Compose profile:** A label that makes some services optional (e.g., `--profile n8n`).
- **WSL2:** Windows Subsystem for Linux. A real Linux kernel inside Windows, which Docker uses on Windows.
- **Rancher Desktop:** An open-source app that installs and runs Docker (engine + CLI + compose) on Windows.
- **Multi-stage build:** A Dockerfile that builds in one stage and copies only what's needed into a small final image.
- **ruff:** A very fast Python linter + formatter.
- **pytest:** The Python testing framework. *Unit tests* check small pieces in isolation. *Integration tests* check pieces working together (with real services).
- **End-to-end (E2E) test:** A test that drives the real app the way a person would (a real browser clicking and typing), through the UI, API, databases and the LLM. It catches problems unit tests can't, like two parts that each work alone but clash together.
- **Playwright:** The tool that runs our E2E tests. It controls a headless Chromium browser, takes screenshots and records a step-by-step "trace" when a test fails.
- **Headless browser:** A real browser running without a visible window, so tests can run unattended.
- **Race condition:** A bug that depends on timing: which of two things finishes first. Our E2E tests found three, all versions of "a slow first load overwrites something newer the user just did".
- **Flaky test:** A test that sometimes passes and sometimes fails without any code change, usually because of timing. We run the E2E suite twice to check it's stable.
- **Regression test that proves itself:** After writing a test for a bug, remove the fix and check the test *fails*. Otherwise the test may guard nothing (this happened with our StrictMode test until we fixed it).
- **Mock / fake:** A stand-in object used in tests (e.g., a fake LLM that returns fixed answers).
- **Side effect at import:** When merely importing a library *does* something (here: `magika`, used by MarkItDown, copied our whole `.env` into the environment). Good libraries avoid it; we defend against it with a test.
- **Environment inheritance:** A program you start (a "child process") receives a copy of your environment variables. That's why secrets must not sit in `os.environ` unnecessarily.
- **`tmp_path` (pytest):** A fresh empty folder per test, deleted afterwards. Perfect for creating broken or empty files to test error handling.
- **Parametrised test:** One test function run several times with different inputs (`@pytest.mark.parametrize`).
- **Shallow clone:** Downloading only the latest version of a repo (`--depth=1`), not its whole history. Much faster and smaller.
- **SSRF (Server-Side Request Forgery):** Tricking a server into fetching a URL of the attacker's choice (e.g. an internal admin page). We prevent it by accepting only `https://github.com/<owner>/<repo>`.
- **Symlink:** A file that points to another file. A malicious repo could use one to point at files outside the repo, so clones disable symlinks and skip them.
- **Path traversal:** An uploaded file named `../../something` trying to write outside the upload folder. We keep only the final name part.
- **subprocess (no shell):** Running a program (here `git`) with its arguments as a list. Nothing in the arguments can be interpreted as extra commands.
- **Background job / worker:** Slow work (ingestion) handed to a separate thread. The API answers immediately with a job id (`202 Accepted`) and the client polls for status.
- **HTTP status codes:** 200 OK, 202 Accepted (work queued), 400 bad request, 404 not found, 413 too large, 415 unsupported type, 422 invalid input, 503 not ready.
- **Multipart upload:** The standard way browsers send files to a server in a POST request.
- **Lazy initialisation:** Creating something expensive (a model, a connection pool) only the first time it is needed, then reusing it.
- **Fixture (pytest):** A reusable piece of test setup (e.g., `client`, `settings` in `tests/conftest.py`). pytest passes it to any test that names it as a parameter.
- **Marker (pytest):** A label on a test (`@pytest.mark.integration`) used to select or skip groups of tests. A plain `pytest` skips `integration` and `openai` tests, so it is fast and free.
- **TestClient:** FastAPI's tool for calling your API in tests without starting a real server.
- **`pyproject.toml`:** The standard config file for Python tools. Ours configures ruff and pytest.
- **`.dockerignore`:** Lists files Docker must never copy into an image (e.g., `.env`, `.venv`).
- **Named volume:** A Docker volume with a name (`postgres_data`) that keeps data when containers are removed. Only `docker compose down -v` deletes it.
- **Binding to `127.0.0.1`:** Makes a port reachable only from your own laptop, not from other devices on your Wi-Fi.
- **Loopback / `127.0.0.1` vs `localhost`:** Both mean "this computer". But `localhost` resolves to *two* addresses: IPv4 `127.0.0.1` and IPv6 `::1`. Some drivers try `::1` first. Our containers only listen on IPv4, so that attempt hangs until a timeout. That's why our settings use `127.0.0.1` (the Phase 1 Postgres bug: 8 s → 0.02 s).
- **IPv4 / IPv6:** Two versions of internet addresses. IPv4 looks like `127.0.0.1`; IPv6 looks like `::1`.
- **Docker Desktop:** Docker's app for Windows/macOS. It runs the Docker engine inside a small Linux VM on WSL2 (the `docker-desktop` distribution).
- **Feature branch:** A git branch for one piece of work (`session-1`). It is merged into `main` via a pull request once its checks pass.
- **Pull request (PR):** A request on GitHub to merge a branch into `main`, where the changes can be reviewed first.

## Evaluation & automation (stretch)

- **Faithfulness:** Whether the answer's claims are supported by the retrieved context (the opposite of hallucination).
- **Answer relevancy:** Whether the answer actually addresses the question.
- **Bias (in evaluation):** Unfair or stereotyped content in answers, measured with probe questions and a judge.
- **Regression:** A change that makes quality worse than before. Evals catch it.
- **DeepEval:** An open-source library of LLM evaluation metrics.
- **n8n:** A visual workflow automation tool (connect triggers to actions).
- **Webhook:** A URL that another system calls to notify you of an event.
- **Fair-code licence:** Source is visible and free for many uses, but with restrictions, so it is not "open source" by the OSI definition. n8n uses one.
