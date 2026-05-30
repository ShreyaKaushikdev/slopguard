"""Adversarial Slop Detection — Specificity Verifier.

Sits on top of the WHY/WHAT classifier. When a sentence is classified as WHY
(causal reasoning), this layer asks: is the reasoning actually specific and
falsifiable, or is it generic reasoning theater?

Core logic:
1. Extract the causal clause from WHY-classified sentences
2. Score specificity using falsifiability markers
3. Blend with WHY confidence to penalize unfalsifiable reasoning
4. Return flagged claims, strong claims, and a composite score
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

# ============================================================================
# Causal connectives (used to split WHY sentences into claim + reasoning)
# ============================================================================

_CAUSAL_CONNECTIVES = re.compile(
    r"\s+\bbecause\b"
    r"|\s+\bsince\b"
    r"\s+\bso\b"
    r"\s+\btherefore\b"
    r"\s+\bthus\b"
    r"\s+\bhence\b"
    r"\s+\bdue to\b"
    r"\s+\bas a result\b"
    r"\s+\bin order to\b"
    r"\s+\bto\b(?!\s+(be|do|make|get|have|use))"
    r"\s+\bfor\b(?!\s+(example|instance|this\s+reason))"
    r"|\s+\bwhich\b"
    r"|\s+\bthat\b(?!\s+means|'\s)"
    # Em-dash and en-dash as reasoning separators (e.g. "Fixed X — previous impl did Y")
    r"|\s*[—–]\s*"
    r"|\s*---\s*",
    re.I,
)

_HEDGE_WORDS = {
    "might", "could", "potentially", "possibly", "seems", "appears",
    "perhaps", "maybe", "somewhat", "relatively", "generally", "typically",
    "usually", "often", "likely", "unlikely", "probably",
}

_TAUTOLOGICAL_PATTERNS = [
    re.compile(r"\b(\w+)\s+to\s+(fix|resolve|improve|update|change)\s+\1\b", re.I),
    re.compile(r"\bupdated\s+(\w+)\s+because\s+\1\b", re.I),
    re.compile(r"\bchanged\s+(\w+)\s+to\s+fix\s+\1\b", re.I),
    re.compile(r"\b(\w+)\s+(is|was)\s+\1(?:er|ed)?\b", re.I),
]

# ============================================================================
# High specificity markers
# ============================================================================

_NUMERIC_WITH_UNITS = re.compile(
    r"\d+(?:\.\d+)?\s*(?:ms|s|sec|min|hr|hour|kb|mb|gb|tb|px|%|x|times|deg|fps|"
    r"requests?/sec|rps|ops|qps|mb/s|gb/s|ns|μs|us|seconds?|minutes?|hours?|"
    r"bytes?|kilobytes?|megabytes?|gigabytes?|terabytes?|"
    r"milliseconds?|microseconds?|nanoseconds?|"
    r"lines?|chars?|chars?/sec|words?|tokens?|"
    r"deps?|dependencies?|files?|modules?|packages?|"
    r"users?|accounts?|sessions?|connections?|"
    r"requests?|responses?|queries?|mutations?|"
    r"rows?|records?|entries?|items?|"
    r"clusters?|nodes?|pods?|instances?|"
    r"threads?|processes?|goroutines?|"
    r"ms\b|kb\b|mb\b|gb\b|tb\b|\d+x\b|\d+%)",
    re.I,
)

_VERSION_PATTERN = re.compile(r"\b(?:v|version)\s*\d+\.\d+", re.I)
_NODE_VERSION = re.compile(r"\bnode\s*\d+\.\d+", re.I)
_PYTHON_VERSION = re.compile(r"\bpython\s*\d+\.\d+", re.I)

_FILE_PATH = re.compile(
    r"(?:^|[\s/])(?:[a-zA-Z0-9_.-]+/)*[a-zA-Z0-9_.-]+\.(?:js|ts|tsx|jsx|py|rb|go|rs|java|"
    r"c|cpp|h|hpp|cs|rb|php|sh|bash|zsh|fish|ps1|bat|cmd|yaml|yml|json|toml|"
    r"ini|cfg|conf|env|html|css|scss|sass|less|svg|md|rst|txt|log|lock|"
    r"gitignore|dockerignore|env\.\w+)"
    r"|\b[a-zA-Z0-9_.-]+/(?:[a-zA-Z0-9_.-]+/)*[a-zA-Z0-9_.-]+\b"
    r"|/\b[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)+",
)

_ERROR_CODE = re.compile(
    r"(?:TypeError|SyntaxError|ReferenceError|RangeError|TypeError|URIError|"
    r"ValueError|KeyError|IndexError|AttributeError|ImportError|"
    r"FileNotFoundError|ModuleNotFoundError|StopIteration|"
    r"CVE-\d{4}-\d{4,}|PR-\d{3,}|GH-\d{3,}|SEC-\d{3,}|"
    r"error\s*(?:code\s*)?#?\d{3,}|"
    r"status\s*(?:code\s*)?\d{3}|"
    r"exit\s*code\s*\d+|"
    r"(?:HTTP|https?)\s*(?:status\s*)?(?:code\s*)?\d{3}|"
    r"issue\s*#?\d{2,}|\bfixes?\s*#?\d{2,}|\bcloses?\s*#?\d{2,}|"
    # Line number references are highly specific
    r"line\s+\d+|"
    r"lines?\s+\d+(?:\s*[-–]\s*\d+)?)",
    re.I,
)

_TOOL_REFERENCE = re.compile(
    r"\b(?:profiling|benchmark|test output|test suite|linter|eslint|prettier|"
    r"prettier|webpack|rollup|vite|esbuild|tsc|babel|jest|mocha|pytest|"
    r"cargo|npm|yarn|pnpm|pip|docker|kubernetes|kubectl|helm|terraform|"
    r"ansible|jenkins|github actions|ci/cd|coverage|codecov|sonar|"
    r"bundle\s*(?:analysis|size|analyzer)|heap\s*(?:dump|profile)|"
    r"flamegraph|flame\s*graph|perf|performance\s*(?:test|audit|insight)|"
    r"devtools|chrome\s*(?:dev)?tools|firefox\s*devtools|"
    r"network\s*(?:tab|panel|log)|console\.(?:log|warn|error|debug)|"
    r"linting|static\s*analysis|type\s*check(?:ing)?|"
    r"tree[- ]shak(?:e|ing)|code\s*split(?:ting)?|dead\s*code|"
    r"main\s*chunk|vendor\s*chunk|asset\s*module|"
    r"hot\s*module\s*replacement|HMR|live\s*reload|"
    r"source\s*map|minif(?:y|ication)|transpil(?:e|ation)|"
    r"memoiz(?:e|ation)|debounce|throttle|"
    r"cache\s*(?:hit|miss|invalidation|busting)|"
    # Cloud services and observability tools
    r"cloudwatch|datadog|splunk|grafana|prometheus|sentry|pagerduty|"
    r"new\s*relic|dynatrace|elastic(?:search)?|kibana|logstash|"
    r"s3|ec2|lambda|rds|dynamodb|sqs|sns|cloudfront|"
    r"gcs|bigquery|pubsub|cloud\s*run|"
    r"azure\s*(?:monitor|devops|functions|blob)|"
    r"supabase|firebase|vercel|netlify|heroku|"
    r"nginx|apache|haproxy|traefik|envoy|istio)\b",
    re.I,
)

_NAMED_CODEBASE_ENTITY = re.compile(
    r"(?:function|class|method|component|hook|route|endpoint|handler|"
    r"middleware|plugin|module|service|controller|repository|factory|"
    r"provider|injector|decorator|directive|filter|interceptor|"
    r"resolver|serializer|validator|formatter|parser|compiler|"
    r"transformer|mapper|adapter|wrapper|proxy|stub|mock|fixture|"
    r"test\s*\w+|spec\s*\w+)\s+['\"]?([a-zA-Z_]\w{2,50})['\"]?"
    r"|use[A-Z][a-zA-Z]{2,50}"
    r"|_[a-z][a-z_]{2,50}"
    r"|__[a-z_]{2,50}__",
    re.I,
)

_TIMESTAMP_REFERENCE = re.compile(
    r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"today|yesterday|last\s+(?:week|month|quarter|year|sprint)|"
    r"this\s+(?:week|month|quarter|year|sprint)|"
    r"after\s+(?:the\s+)?(?:deploy|release|merge|push|update|upgrade|migration)|"
    r"before\s+(?:the\s+)?(?:deploy|release|merge|push|update|upgrade|migration)|"
    r"during\s+(?:the\s+)?(?:deploy|release|merge|push|update|upgrade|migration)|"
    r"since\s+(?:version|v|release)\s*[\d.]+)\b",
    re.I,
)

# --- Additional high-specificity patterns ---

_ARCHITECTURAL_PATTERNS = re.compile(
    r"\b(?:singleton|observer\s*pattern|factory\s*(?:method)?|"
    r"abstract\s*factory|builder\s*pattern|prototype\s*pattern|"
    r"strategy\s*pattern|command\s*pattern|adapter\s*pattern|"
    r"decorator\s*pattern|facade\s*pattern|proxy\s*pattern|"
    r"bridge\s*pattern|composite\s*pattern|flyweight\s*pattern|"
    r"chain\s*of\s*responsibility|mediator\s*pattern|"
    r"interpreter\s*pattern|iterator\s*pattern|visitor\s*pattern|"
    r"mvc|mvvm|mvp|flux|redux|vuex|ngrx|"
    r"circuit\s*breaker|event\s*sourcing|CQRS|"
    r"saga\s*pattern|two[- ]phase\s*commit|"
    r"pub[- ]?sub|message\s*queue|event\s*bus|"
    r"dependency\s*injection|inversion\s*of\s*control|"
    r"repository\s*pattern|unit\s*of\s*work|"
    r"service\s*layer|domain\s*driven\s*design|"
    r"hexagonal\s*architecture|ports\s*and\s*adapters|"
    r"microservice|serverless|edge\s*function|"
    r"API\s*gateway|BFF|backend\s*for\s*frontend)\b",
    re.I,
)

_FAILURE_MODES = re.compile(
    r"\b(?:race\s*condition|deadlock|livelock|starvation|"
    r"memory\s*leak|buffer\s*overflow|null\s*(?:pointer\s*)?(?:exception|dereference)|"
    r"off[- ]by[- ]one|N\s*[+−]?\s*1|N\+1\s*query|"
    r"thundering\s*herd|cache\s*(?:storm|avalanche|miss|hit|poisoning)|"
    r"connection\s*(?:pool\s*(?:exhaustion)?|leak|timeout|reset)|"
    r"socket\s*(?:hang\s*up|timeout|refused|error)|"
    r"dns\s*(?:resolution|lookup|failure)|"
    r"SSL|TLS|certificate\s*(?:pinning|expiry|validation)|"
    r"XSS|CSRF|SQL\s*injection|CORS\s*(?:error|policy)|"
    r"stack\s*overflow|heap\s*(?:corruption|exhaustion)|"
    r"thread\s*safety|reentrancy|idempotency|"
    r"blocking\s*(?:call|I\/?O)|non[- ]blocking|"
    r"backpressure|congestion\s*control)\b",
    re.I,
)

_COMPARATIVE_ALTERNATIVES = re.compile(
    r"\b(?:instead\s*of|unlike|replacing|replaced\s*(?:with|by)|"
    r"swapped\s*(?:for|with)|migrating\s*(?:from|to)|"
    r"switching\s*(?:from|to)|moving\s*(?:from|to)|"
    r"different\s*(?:from|than)|alternative\s*to)\b",
    re.I,
)

_LIBRARY_OR_PACKAGE = re.compile(
    r"\b(?:moment\.?js|date[- ]fns|dayjs|luxon|lodash|underscore|"
    r"axios|fetch|node[- ]fetch|got|request|"
    r"express|fastify|koa|hapi|nestjs|"
    r"react|vue|angular|svelte|solid|"
    r"redux|mobx|zustand|recoil|jotai|"
    r"webpack|rollup|vite|esbuild|parcel|"
    r"jest|mocha|vitest|cypress|playwright|"
    r"prisma|sequelize|typeorm|drizzle|knex|"
    r"redis|memcached|kafka|rabbitmq|zeromq|"
    r"postgres|mysql|sqlite|mongodb|dynamodb|"
    r"stripe|twilio|sendgrid|auth0|firebase|"
    r"aws|azure|gcp|cloudflare|vercel|netlify)\b",
    re.I,
)

# ============================================================================
# Medium specificity markers
# ============================================================================

_COMPARATIVE_MEASUREMENT = re.compile(
    r"\b(?:significantly|substantially|considerably|dramatically|noticeably|"
    r"measurably|markedly|vastly)\s+(?:faster|slower|larger|smaller|"
    r"better|worse|more|less|higher|lower|improved|reduced|increased)\b"
    r"|\b(?:reduced|increased|improved|decreased)\s+by\s+(?:half|a\s+third|"
    r"a\s+quarter|double|triple|\d+\s*%?)\b"
    r"|\b(?:faster|slower|better|worse|larger|smaller)\s+than\s+\b",
    re.I,
)

_NAMED_PATTERN = re.compile(
    r"\b(?:race\s*condition|n\s*[-+]?\s*1\s+query|memory\s*leak|"
    r"buffer\s*overflow|null\s*pointer|off\s*by\s*one|"
    r"deadlock|livelock|starvation|thundering\s*herd|"
    r"cache\s*(?:in)?validation|cache\s*miss|cache\s*hit|"
    r"salt(?:ing)?|hash(?:ing)?|encrypt(?:ion)?|decrypt(?:ion)?|"
    r"middleware|interceptor|decorator|singleton|factory\s*method|"
    r"observer\s*pattern|proxy\s*pattern|adapter\s*pattern|"
    r"dependency\s*injection|inversion\s*of\s*control|"
    r"solid\s*principles|dry\s*principle|kiss\s*principle|"
    r"separation\s*of\s*concerns|single\s*responsibility|"
    r"open[/-]closed\s*principle|liskov\s*substitution|"
    r"interface\s*segregation|dependency\s*inversion)\b",
    re.I,
)

_TICKET_OR_PERSON = re.compile(
    r"(?:fixes|closes|resolves|addresses|refs?|related\s+to)\s*#?\d{2,}"
    r"|per\s+[A-Z][a-z]+(?:'[s])?"
    r"|per\s+(?:alice|bob|charlie|dave|eve|frank|grace|heidi|ivan|judy|karl|mallory|oscar|peggy|trent|walter|wendi)"
    r"|per\s+code\s*review"
    r"|as\s+suggested\s+by\s+[A-Z][a-z]+"
    r"|requested\s+by\s+[A-Z][a-z]+",
    re.I,
)

# ============================================================================
# Low specificity markers (unfalsifiable)
# ============================================================================

_PURE_ADJECTIVES = re.compile(
    r"\b(?:slow|fast|messy|clean|unclear|clear|better|worse|good|bad|"
    r"nice|ugly|complex|simple|easy|hard|difficult|straightforward|"
    r"elegant|robust|solid|reliable|flexible|scalable|maintainable|"
    r"readable|efficient|optimized|performant|improved|enhanced|"
    r"modern|legacy|old|new|fresh|stale|current|latest)\b",
    re.I,
)

_GENERIC_IMPROVEMENT = re.compile(
    r"\b(?:improves?\s+performance|enhances?\s+readability|"
    r"better\s+maintainability|cleaner\s+approach|"
    r"more\s+efficient|more\s+robust|more\s+reliable|"
    r"improved\s+user\s*experience|enhanced\s+functionality|"
    r"better\s+code\s*quality|improved\s+architecture|"
    r"enhanced\s+security|better\s+error\s*handling|"
    r"improved\s+scalability|better\s+performance)\b",
    re.I,
)

_VAGUE_REFERENCES = re.compile(
    r"\b(?:various|several|multiple|many|some|different|certain|"
    r"appropriate|suitable|relevant|related|corresponding)\b"
    r"\s+(?:reasons?|issues?|problems?|bugs?|changes?|updates?|"
    r"improvements?|fixes?|additions?|removals?|adjustments?)\b",
    re.I,
)

# ============================================================================
# AI slop fingerprint patterns
# These detect prompt-engineered text that tries to appear specific but is
# actually generic reasoning theater. Common in AI-generated PRs, docs, etc.
# ============================================================================

_AI_SLOP_PATTERNS = re.compile(
    r"\b(?:in today's\s*(?:fast[- ]paced\s*)?world|"
    r"it(?:'s|\s+is)\s+(?:important|crucial|essential|worth\s+noting)\s+(?:to\s+)?note|"
    r"dive\s+(?:deep\s+)?(?:into|in)|"
    r"let(?:'s|\s+us)\s+(?:dive|explore|delve)|"
    r"in\s+this\s+(?:article|blog\s*post|guide|tutorial|deep\s*dive)|"
    r"whether\s+you(?:'re|\s+are)\s+a\s+(?:seasoned|beginner|junior|senior)|"
    r"buckle\s+up|"
    r"without\s+further\s+ado|"
    r"at\s+the\s+end\s+of\s+the\s+day|"
    r"in\s+conclusion|to\s+(?:sum\s+up|wrap\s+up|conclude)|"
    r"delve\s+(?:into|deeper)|"
    r"a\s+testament\s+to|"
    r"tapestry\s+(?:of|in)|"
    r"rich\s+(?:history|ecosystem|landscape|tapestry)|"
    r"game[- ]changer|game[- ]changing|"
    r"cutting[- ]edge|state[- ]of[- ]the[- ]art|"
    r"revolutionize|transformative|paradigm\s*shift|"
    r"robust\s+(?:solution|framework|toolset|architecture)|"
    r"seamless\s*(?:integration|experience|workflow)|"
    r"empower(?:s|ing|ed)?\s+(?:users|teams|developers|organizations)|"
    r"harness\s+(?:the\s+power\s+of|the\s+potential\s+of)|"
    r"unlock\s+(?:the\s+potential|new\s+possibilities|insights)|"
    r"streamline\s+(?:your|the)\s+(?:workflow|process|operations)|"
    r"leverage\s+(?:our|this|the)\s+(?:powerful|robust|advanced)|"
    r"comprehensive\s+(?:guide|solution|overview|analysis)|"
    r"nuanced\s+(?:understanding|approach|perspective)|"
    r"intricate\s+(?:details|relationship|web|dance)|"
    r"meticulously\s+(?:crafted|designed|curated)|"
    r"testament\s+(?:to\s+the|of\s+the)|"
    r"stands\s+as\s+a\s+testament|"
    r"plays\s+a\s+(?:crucial|vital|pivotal|essential)\s+role|"
    r"it\s+is\s+worth\s+noting\s+that|"
    r"it\s+is\s+important\s+to\s+(?:note|understand|recognize)|"
    r"as\s+(?:an?\s+)?AI\s+(?:language\s+)?model|"
    r"as\s+a\s+(?:large|generative)\s+(?:language|AI)\s+model)\b",
    re.I,
)

# Patterns that try to fake specificity but are actually hollow
_FAKE_SPECIFICITY = re.compile(
    r"\b(?:some\s+(?:users|people|developers|teams)|"
    r"certain\s+(?:cases?|scenarios?|situations?|conditions?)|"
    r"in\s+(?:some|many|most|various|certain)\s+(?:cases?|instances?|situations?)|"
    r"(?:can|could|may|might)\s+(?:potentially|possibly|perhaps|likely)\s+(?:be|improve|help|provide)|"
    r"(?:offers?|provides?|delivers?)\s+(?:a\s+)?(?:better|improved|enhanced|superior)\s+(?:experience|solution|approach)|"
    r"(?:aims?\s+to|designed?\s+to|built?\s+to)\s+(?:provide|offer|deliver|enable|support)|"
    r"(?:helps?\s+to?|enables?\s+to?|allows?\s+to?)\s+(?:users?|teams?|developers?)\s+(?:to\s+)?(?:easily|quickly|efficiently|seamlessly))\b",
    re.I,
)

# Hedged causal claims — "because it could potentially..."
_HEDGED_CAUSAL = re.compile(
    r"\b(?:because|since|so|therefore|thus)\s+"
    r"(?:(?:it|this|that)\s+)?"
    r"(?:may|might|could|can|would|should)\s+"
    r"(?:potentially|possibly|perhaps|likely|somewhat)\s+"
    r"(?:be|help|improve|provide|enable|support|result)",
    re.I,
)

# ============================================================================
# Domain calibration thresholds
# ============================================================================

DOMAIN_THRESHOLDS: dict[str, dict] = {
    "code_review": {
        "high_bar": 0.6,
        "qualitative_floor": 0.35,
        "label": "high",
        "note": "Code reviews should expect filenames, line numbers, benchmarks.",
    },
    "docs": {
        "high_bar": 0.4,
        "qualitative_floor": 0.50,
        "label": "medium",
        "note": "Docs should expect concrete examples and specific instructions.",
    },
    "hiring": {
        "high_bar": 0.4,
        "qualitative_floor": 0.40,
        "label": "medium",
        "note": "Hiring should expect numbers, company names, specific projects.",
    },
    "communications": {
        "high_bar": 0.25,
        "qualitative_floor": 0.50,
        "label": "low",
        "note": "Qualitative reasoning is normal in communications.",
    },
    "content": {
        "high_bar": 0.4,
        "qualitative_floor": 0.40,
        "label": "medium",
        "note": "Content should expect specific claims with evidence.",
    },
    "academia": {
        "high_bar": 0.7,
        "qualitative_floor": 0.35,
        "label": "highest",
        "note": "Every academic claim should be citable.",
    },
    "marketplace": {
        "high_bar": 0.4,
        "qualitative_floor": 0.40,
        "label": "medium",
        "note": "Reviews should expect specific product experiences.",
    },
    "social_news": {
        "high_bar": 0.35,
        "qualitative_floor": 0.40,
        "label": "medium",
        "note": "Social news should expect sourced claims.",
    },
    "general": {
        "high_bar": 0.4,
        "qualitative_floor": 0.40,
        "label": "medium",
        "note": "General content expects moderate specificity.",
    },
}


# ============================================================================
# Data structures
# ============================================================================

@dataclass
class ClaimVerdict:
    sentence: str
    why_confidence: float
    specificity: float
    verdict: Literal["specific_reasoning", "generic_reasoning", "unfalsifiable_reasoning", "qualitative_reasoning"]
    suggestion: str = ""
    markers_found: list[str] = field(default_factory=list)
    low_markers_found: list[str] = field(default_factory=list)


# ============================================================================
# Core functions
# ============================================================================

def extract_causal_clause(sentence: str) -> tuple[str, str]:
    """Split a WHY sentence into action and reasoning clause.

    Returns (action, reasoning). If no causal connective found,
    returns (sentence, "").
    """
    match = _CAUSAL_CONNECTIVES.search(sentence)
    if match:
        action = sentence[:match.start()].strip()
        reasoning = sentence[match.end():].strip()
        return action, reasoning
    return sentence, ""


def _count_specificity_markers(reasoning: str) -> tuple[int, int, int, list[str]]:
    """Count high, medium, low specificity markers in a reasoning clause.

    Returns (high_count, medium_count, low_count, high_marker_names).
    """
    high_count = 0
    medium_count = 0
    low_count = 0
    high_markers = []

    # --- High specificity ---
    if _NUMERIC_WITH_UNITS.search(reasoning):
        high_count += 1
        high_markers.append("numeric_measurement")

    if _FILE_PATH.search(reasoning):
        high_count += 1
        high_markers.append("file_path")

    if _ERROR_CODE.search(reasoning):
        high_count += 1
        high_markers.append("error_code_or_identifier")

    if _TOOL_REFERENCE.search(reasoning):
        high_count += 1
        high_markers.append("tool_reference")

    if _VERSION_PATTERN.search(reasoning) or _NODE_VERSION.search(reasoning) or _PYTHON_VERSION.search(reasoning):
        high_count += 1
        high_markers.append("version_reference")

    if _NAMED_CODEBASE_ENTITY.search(reasoning):
        high_count += 1
        high_markers.append("named_codebase_entity")

    if _TIMESTAMP_REFERENCE.search(reasoning):
        high_count += 1
        high_markers.append("timestamp_reference")

    if _ARCHITECTURAL_PATTERNS.search(reasoning):
        high_count += 1
        high_markers.append("architectural_pattern")

    if _FAILURE_MODES.search(reasoning):
        high_count += 1
        high_markers.append("failure_mode")

    if _COMPARATIVE_ALTERNATIVES.search(reasoning):
        high_count += 1
        high_markers.append("comparative_alternative")

    if _LIBRARY_OR_PACKAGE.search(reasoning):
        high_count += 1
        high_markers.append("library_or_package")

    # --- Medium specificity ---
    if _COMPARATIVE_MEASUREMENT.search(reasoning):
        medium_count += 1

    if _NAMED_PATTERN.search(reasoning):
        medium_count += 1

    if _TICKET_OR_PERSON.search(reasoning):
        medium_count += 1

    # --- Low specificity ---
    tautology_found = any(p.search(reasoning) for p in _TAUTOLOGICAL_PATTERNS)
    if tautology_found:
        low_count += 1

    pure_adj = _PURE_ADJECTIVES.findall(reasoning)
    if pure_adj:
        low_count += len(pure_adj)

    generic = _GENERIC_IMPROVEMENT.findall(reasoning)
    if generic:
        low_count += len(generic)

    vague = _VAGUE_REFERENCES.findall(reasoning)
    if vague:
        low_count += len(vague)

    # Check for hedge words
    words = set(re.findall(r"\b\w+\b", reasoning.lower()))
    hedge_hits = words & _HEDGE_WORDS
    if hedge_hits:
        low_count += len(hedge_hits)

    # AI slop fingerprint — heavy penalty for cliché AI phrasing
    ai_slop_hits = _AI_SLOP_PATTERNS.findall(reasoning)
    if ai_slop_hits:
        low_count += len(ai_slop_hits) * 2  # Double penalty for AI slop patterns

    # Fake specificity — tries to sound specific but is hollow
    fake_spec = _FAKE_SPECIFICITY.findall(reasoning)
    if fake_spec:
        low_count += len(fake_spec)

    # Hedged causal claims — "because it could potentially help..."
    if _HEDGED_CAUSAL.search(reasoning):
        low_count += 2

    return high_count, medium_count, low_count, high_markers


def codebase_aware_boost(reasoning_clause: str, context_text: str = "") -> float:
    """Boost specificity when reasoning mentions entities from the context (e.g. diff).

    Checks whether tokens in the reasoning clause overlap with code entities
    in the context text. Returns a boost up to +0.30.
    """
    if not context_text:
        return 0.0

    # Extract code entities from context: identifiers, file names, etc.
    context_tokens = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", context_text))
    clause_tokens = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", reasoning_clause))
    overlap = clause_tokens & context_tokens

    # Filter out common English words from overlap
    common = {
        "this", "that", "from", "with", "have", "been", "were", "will",
        "would", "could", "should", "because", "which", "their", "there",
        "about", "after", "before", "between", "through", "during",
    }
    meaningful_overlap = overlap - common

    boost = min(0.30, len(meaningful_overlap) * 0.08)
    return boost


def score_specificity(reasoning: str, context_text: str = "") -> float:
    """Score a reasoning clause for specificity/falsifiability.

    Returns a float in [0.0, 1.0] where:
    - 0.0-0.25 = unfalsifiable (pure adjectives, generic language)
    - 0.40-0.65 = medium (comparative, named patterns, tickets)
    - 0.75-1.0 = high (numbers with units, file paths, tool output)
    """
    if not reasoning or len(reasoning.split()) < 2:
        return 0.15  # Too short to be specific

    high_count, medium_count, low_count, high_markers = _count_specificity_markers(reasoning)

    # Weighted scoring — more aggressive for multiple markers
    high_score = min(high_count * 0.15, 1.0)
    medium_score = min(medium_count * 0.12, 0.6)
    low_penalty = min(low_count * 0.10, 0.4)

    # Base scoring with better separation
    if high_count >= 3:
        # Very high specificity: multiple concrete markers
        base = min(0.85, 0.55 + high_count * 0.10)
    elif high_count >= 2:
        # High specificity
        base = min(0.78, 0.45 + high_count * 0.12)
    elif high_count == 1:
        # Single high marker
        base = max(0.55, high_score)
    elif medium_count >= 2:
        # Multiple medium markers
        base = max(0.50, medium_score)
    elif medium_count == 1:
        # Single medium marker
        base = max(0.40, medium_score)
    else:
        # No specificity markers
        base = 0.12

    # Apply low specificity penalty
    final = max(0.0, base - low_penalty)

    # Codebase-aware boost
    boost = codebase_aware_boost(reasoning, context_text)
    final = min(1.0, final + boost)

    return round(final, 3)


def classify_claim(
    sentence: str,
    why_confidence: float,
    specificity: float,
    domain: str = "general",
) -> ClaimVerdict:
    """Classify a single WHY claim and generate suggestion.

    Returns a ClaimVerdict with verdict and suggestion.
    """
    _, reasoning = extract_causal_clause(sentence)

    # Domain-calibrated verdict
    threshold = DOMAIN_THRESHOLDS.get(domain, DOMAIN_THRESHOLDS["general"])["high_bar"]

    if specificity >= threshold:
        verdict = "specific_reasoning"
        suggestion = ""
    elif specificity >= threshold * 0.5:
        verdict = "generic_reasoning"
        suggestion = "Add specifics — numbers, filenames, or tool output to strengthen this claim."
    elif specificity >= 0.2:
        verdict = "qualitative_reasoning"
        suggestion = "Consider adding measurable details — benchmarks, metrics, or concrete examples."
    else:
        verdict = "unfalsifiable_reasoning"
        _, reasoning_text = extract_causal_clause(sentence)
        if reasoning_text:
            suggestion = f"Add measurement — {reasoning_text[:60]}? Under what conditions?"
        else:
            suggestion = "Add measurement — how? Under what conditions?"

    return ClaimVerdict(
        sentence=sentence,
        why_confidence=round(why_confidence, 3),
        specificity=round(specificity, 3),
        verdict=verdict,
        suggestion=suggestion,
    )


def blend_confidence(why_confidence: float, specificity: float, domain: str = "general") -> float:
    """Blend WHY confidence with specificity score.

    Formula: final = why_confidence × (floor + (1 - floor) × specificity)

    The floor is domain-calibrated:
    - code_review/academia: 0.35 (high bar, qualitative reasoning less protected)
    - docs/communications: 0.50 (qualitative reasoning normal, higher floor)
    - others: 0.40 (balanced)

    This means:
    - High specificity (1.0): keeps 100% of WHY credit
    - Zero specificity (0.0): keeps floor% of WHY credit
    - The floor preserves genuine qualitative reasoning (UX, design decisions)
    """
    floor = DOMAIN_THRESHOLDS.get(domain, DOMAIN_THRESHOLDS["general"]).get("qualitative_floor", 0.40)
    return round(why_confidence * (floor + (1.0 - floor) * specificity), 4)


def verify_reasoning(
    sentences: list[str],
    why_confidences: list[float],
    domain: str = "general",
    context_text: str = "",
) -> tuple[float, list[ClaimVerdict], list[ClaimVerdict]]:
    """Verify reasoning specificity for a list of WHY-classified sentences.

    Args:
        sentences: List of sentences classified as WHY.
        why_confidences: Corresponding WHY confidence scores from the classifier.
        domain: Domain for threshold calibration.
        context_text: Optional context (e.g. diff) for codebase-aware specificity boost.

    Returns:
        (composite_why_score, flagged_claims, strong_claims)
    """
    if not sentences:
        return 0.5, [], []

    flagged: list[ClaimVerdict] = []
    strong: list[ClaimVerdict] = []
    blended_scores: list[float] = []

    for sentence, confidence in zip(sentences, why_confidences):
        _, reasoning = extract_causal_clause(sentence)
        if not reasoning:
            # No causal clause — treat as low specificity
            specificity = 0.25
        else:
            specificity = score_specificity(reasoning, context_text)

        final_score = blend_confidence(confidence, specificity, domain)
        blended_scores.append(final_score)

        verdict = classify_claim(sentence, confidence, specificity, domain)
        verdict.specificity = specificity
        verdict.sentence = sentence

        if verdict.verdict in ("unfalsifiable_reasoning", "generic_reasoning"):
            flagged.append(verdict)
        else:
            strong.append(verdict)

    # Composite: average of blended scores
    composite = sum(blended_scores) / len(blended_scores) if blended_scores else 0.5

    return round(composite, 4), flagged, strong


def ai_slop_fingerprint(text: str) -> dict:
    """Detect AI slop fingerprint patterns in text.

    Returns a dict with:
    - slop_score: 0.0 (clean) to 1.0 (heavy AI slop)
    - patterns_found: list of matched AI slop patterns
    - fake_specificity: list of hollow "specific-sounding" phrases
    - hedged_causal: list of hedged causal claims

    This complements the specificity verifier by catching prompt-engineered
    content that tries to appear thoughtful but uses AI-typical phrasing.
    """
    patterns_found = _AI_SLOP_PATTERNS.findall(text)
    fake_spec = _FAKE_SPECIFICITY.findall(text)
    hedged = _HEDGED_CAUSAL.findall(text)

    # Score: each pattern contributes to slop score
    pattern_weight = len(patterns_found) * 0.15
    fake_weight = len(fake_spec) * 0.10
    hedge_weight = len(hedged) * 0.20

    slop_score = min(1.0, pattern_weight + fake_weight + hedge_weight)

    return {
        "slop_score": round(slop_score, 3),
        "patterns_found": patterns_found[:10],
        "fake_specificity": fake_spec[:5],
        "hedged_causal": hedged[:5],
        "total_signals": len(patterns_found) + len(fake_spec) + len(hedged),
    }
