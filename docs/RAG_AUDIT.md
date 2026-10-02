# RAG Audit Notes

## Verified Flow

Admin-only PDF ingestion validates the filename, media type, size, PDF signature, and required metadata before storing the file. The ingestion path extracts page text, chunks it with configured overlap, creates embeddings, replaces the document's Chroma chunks, and persists relational source metadata. Authenticated users can list source metadata and ask grounded questions. Retrieval supports destination, category, and document-type filters; answers return bounded citations that are checked against retrieved sources. Empty or weak retrieval returns a no-context response, and generation failures return a generic ungrounded response. Groq/Gemini fallback is handled by the shared LLM loader.

Automated tests cover PDF ingestion and indexing with controlled providers, chunking, Chroma persistence boundaries, retrieval filters, citations, empty retrieval, and generation failure. Live provider behavior was not tested in this audit.

## Known Limitations

- Metadata filters are case-insensitive through case-folding; they are not fuzzy-matched.
- Existing knowledge-source metadata cannot be edited through the current admin API; reindexing reuses the stored metadata.
- A failure between Chroma, the relational database, and filesystem operations can leave orphaned vector chunks, a source row, or a physical PDF. These stores do not share a transaction.
- PDF extraction quality depends on extractable text; OCR for scanned pages is not provided.
- No live Groq, Gemini, Tavily, OpenWeather, currency, Chroma/embedding-provider, or production PDF-provider test was run.
