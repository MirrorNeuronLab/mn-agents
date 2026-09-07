"""Persisted, domain-neutral plan/execute cycle for a checkpoint's data map."""


class PhaseCycle:
    def __init__(self, data, *, max_actions=6):
        if type(max_actions) is not int or max_actions < 1:
            raise ValueError("max_actions must be positive")
        self.state = data.setdefault(
            "cycle", {"phase": "planning", "plans": [], "outcomes": [], "actions": 0}
        )
        self.max_actions = max_actions

    @property
    def phase(self):
        return self.state["phase"]

    def start(self, plan):
        if self.phase != "planning":
            raise ValueError("review the active plan before starting another")
        self.state["plans"].append(plan)
        self.state.update(phase="execution", actions=0)

    def require_execution(self):
        if self.phase != "execution":
            raise ValueError("persist an enquiry plan before executing tools")
        if self.state["actions"] >= self.max_actions:
            raise ValueError("review this enquiry before requesting more tools")

    def attempted(self):
        self.state["actions"] += 1

    def review(self, outcome):
        if self.phase != "execution":
            raise ValueError("no active enquiry to review")
        self.state["outcomes"].append(outcome)
        self.state.update(phase="planning", actions=0)

    def allowed_actions(self, *, planning, execution, common=(), pending_review=None):
        """Project the same phase policy for model instructions and dispatch."""
        if pending_review is not None:
            return tuple(pending_review)
        selected = planning if self.phase == "planning" else execution
        return tuple(dict.fromkeys((*common, *selected)))
