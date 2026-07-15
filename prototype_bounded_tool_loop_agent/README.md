# Bounded Tool Loop Agent

Implements deterministic plan/action/observation control with finite limits;
browser, RAG, and domain tool behavior are injected by the caller. A `ToolPlan`
may request multiple bounded actions in one strategy iteration.
