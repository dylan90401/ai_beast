# unstructured_api (stub)

Stub surface area for Unstructured's API service.

- Service name: `unstructured-api`
- Intended role: robust parsing/chunking for messy documents before embeddings.
- Current version: **stub placeholder** (nginx static).

When ready:
- Swap to the real Unstructured API image and configure resource limits.
- Wire `scripts/75_rag_ingest.sh` to use Tika/Unstructured as preprocessors.
