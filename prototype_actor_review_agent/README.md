# Actor Review Agent

Owns review lifecycle and failure policy while delegating prompts, actors, and
RAG behavior to an injected review skill. Actor selection and failure policy
may be resolved per call, and `wrap_agent` attaches review to a primary agent.
The review receives that agent's output as `primary_result`, so context builders
can review the completed deterministic result before artifact finalization.
