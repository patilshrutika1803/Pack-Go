# PACK & GO RAG Evaluation

This offline evaluation package measures retrieval and answer quality without
running during normal application tests. The initial corpus is the Goa travel
guide and contains 20 fixed questions covering beaches, attractions, transport,
seasons, activities, food, culture, destination guidance, and planning.

Retrieval metrics use filename/page ground truth where available:

- Precision@K: relevant retrieved results divided by K.
- Recall@K: relevant retrieved results divided by known relevant results.
- Hit rate: cases with at least one relevant result.
- Average distance: raw Chroma distance; lower is closer.

Latency and failure summaries are deterministic utilities. Answer metrics are
separate from production confidence and can be populated by an offline runner
or an explicitly configured evaluation judge. No secrets or live provider calls
are required by the metric tests.

Run a custom evaluation script from the project root and write its JSON output
outside production code. The report values must come from the actual run.