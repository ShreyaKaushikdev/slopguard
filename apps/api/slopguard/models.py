from typing import Literal

from pydantic import BaseModel, Field


Domain = Literal[
    "code_review",
    "docs",
    "hiring",
    "communications",
    "content",
    "academia",
    "marketplace",
    "social_news",
    "general",
]


class TextScoreRequest(BaseModel):
    text: str = Field(..., min_length=1)
    domain: Domain = "general"
    metadata: dict = Field(default_factory=dict)


class PRScoreRequest(BaseModel):
    title: str = ""
    description: str = Field(..., min_length=1)
    diff: str = ""
    comments: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class PRUrlScoreRequest(BaseModel):
    url: str
    token: str = ""


class BatchScoreRequest(BaseModel):
    items: list[TextScoreRequest]


class CitationRequest(BaseModel):
    citations: list[str]


class RepoScoreRequest(BaseModel):
    repo: str
    pull_requests: list[PRScoreRequest] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class FeedbackRequest(BaseModel):
    text: str
    domain: Domain = "general"
    user_label: Literal["slop", "reviewed", "unsure"]
    score: float | None = None
    url: str = ""
    notes: str = ""


class ScoreEventRequest(BaseModel):
    url: str
    domain: Domain = "general"
    score: float
    oversight: str
    title: str = ""


class SignalResult(BaseModel):
    name: str
    score: float
    weight: float
    label: str = ""
    reason: str = ""
    detail: str = ""
    # Adversarial slop detection fields (populated for why_vs_what signal)
    specificity_score: float | None = None
    reasoning_quality: str = ""
    flagged_claims: list[dict] = Field(default_factory=list)
    strong_claims: list[dict] = Field(default_factory=list)

    def model_post_init(self, __context: object) -> None:
        # Do NOT copy detail into reason — detail is internal debug data,
        # reason is the human-readable explanation shown in the UI
        if not self.label:
            if self.score >= 0.65:
                self.label = "strong"
            elif self.score >= 0.42:
                self.label = "mixed"
            else:
                self.label = "weak"


class RelativeScore(BaseModel):
    raw: float
    repo_mean: float | None = None
    repo_percentile: int | None = None
    author_mean: float | None = None
    global_mean: float | None = None
    global_percentile: int | None = None
    verdict: str = "insufficient_data"
    context: str = ""
    baseline_confidence: str = "none"


class ScoreResponse(BaseModel):
    score: float
    oversight: Literal["high", "mixed", "low", "insufficient"]
    domain: Domain
    summary: str
    reasons: list[str]
    signals: list[SignalResult]
    highlights: list[str] = Field(default_factory=list)
    relative: RelativeScore | None = None


class BatchScoreResponse(BaseModel):
    items: list[ScoreResponse]
    clusters: list[dict]


class RepoScoreResponse(BaseModel):
    repo: str
    score: float
    oversight: str
    timeline: list[dict]
    hotspots: list[dict]
    pull_requests: list[ScoreResponse]


class GitHubOAuthRequest(BaseModel):
    code: str
    state: str = ""


class GitHubTimelineRequest(BaseModel):
    token: str
    owner: str
    repo: str
    limit: int = 30


class GitHubVelocityRequest(BaseModel):
    token: str
    owner: str
    repo: str
    limit: int = 30


class SupabaseScoreEvent(BaseModel):
    user_id: str
    url: str
    title: str = ""
    domain: Domain = "general"
    score: float
    oversight: str
    notes: str = ""


class SupabaseFeedback(BaseModel):
    user_id: str
    event_id: str
    user_label: str
    notes: str = ""


class UserProfileRequest(BaseModel):
    user_id: str
    preferences: dict = {}
