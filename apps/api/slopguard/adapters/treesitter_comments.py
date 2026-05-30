"""Tree-sitter AST parsing for code comment intelligence.

When tree-sitter and language grammars are installed, this module parses
code diffs using AST traversal to extract comments and correlate them
with the code they describe. Falls back to regex-based extraction.

Supported languages:
- Python (tree-sitter-python)
- JavaScript (tree-sitter-javascript)
- TypeScript (tree-sitter-typescript)
- Go (tree-sitter-go)
- Java (tree-sitter-java)
- Rust (tree-sitter-rust)
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_parsers: dict[str, object] = {}
_loaded = False


def _load_parsers() -> bool:
    """Lazy-load tree-sitter parsers for supported languages."""
    global _loaded, _parsers
    if _loaded:
        return _parsers != {}
    _loaded = True

    try:
        from tree_sitter import Language, Parser

        languages = {}
        parser_map = {}

        # Try to load each language grammar
        lang_modules = {
            "python": "tree_sitter_python",
            "javascript": "tree_sitter_javascript",
            "typescript": "tree_sitter_typescript",
            "go": "tree_sitter_go",
            "java": "tree_sitter_java",
            "rust": "tree_sitter_rust",
        }

        for lang_name, module_name in lang_modules.items():
            try:
                mod = __import__(module_name)
                language = Language(getattr(mod, f"language_{lang_name}")())
                parser = Parser(language)
                languages[lang_name] = language
                parser_map[lang_name] = parser
                logger.debug("Loaded tree-sitter parser for %s", lang_name)
            except (ImportError, AttributeError) as exc:
                logger.debug("Could not load tree-sitter %s: %s", lang_name, exc)

        _parsers = parser_map
        return len(_parsers) > 0
    except ImportError:
        logger.debug("tree-sitter not installed; using regex fallback")
        return False


def _detect_language(diff: str) -> str:
    """Heuristically detect the programming language of a diff."""
    lines = diff.splitlines()
    indicators = {
        "python": ("def ", "class ", "import ", "from ", "self.", "__init__", "#"),
        "javascript": ("function ", "const ", "let ", "var ", "=>", "//", "export "),
        "typescript": ("interface ", "type ", ": string", ": number", ": boolean", "//"),
        "go": ("func ", "package ", "import (", "var ", "//", "type ", "struct {"),
        "java": ("public class", "private ", "protected ", "void ", "//", "import ", "package "),
        "rust": ("fn ", "pub ", "let mut", "impl ", "//", "use ", "struct ", "enum "),
    }

    scores = {lang: 0 for lang in indicators}
    for line in lines:
        stripped = line.lstrip("+").lstrip("-").strip()
        for lang, keywords in indicators.items():
            for kw in keywords:
                if kw in stripped:
                    scores[lang] += 1

    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "python"


def _extract_comments_ast(diff: str, language: str = "python") -> list[dict]:
    """Extract comments using tree-sitter AST parsing."""
    parser = _parsers.get(language)
    if parser is None:
        return _extract_comments_regex(diff)

    try:
        from tree_sitter import Tree

        # Extract only the code lines (strip diff markers)
        code_lines = []
        comment_positions = []
        for i, line in enumerate(diff.splitlines()):
            if line.startswith("+") and not line.startswith("+++"):
                code_lines.append(line[1:])
                comment_positions.append(i)

        code_text = "\n".join(code_lines)
        if not code_text.strip():
            return _extract_comments_regex(diff)

        # Parse the code
        tree: Tree = parser.parse(bytes(code_text, "utf-8"))

        comments = []
        comment_types = {"comment", "line_comment", "block_comment", "multiline_comment"}

        def _walk(node):
            if node.type in comment_types:
                text = node.text.decode("utf-8", errors="replace")
                comments.append({"text": text, "type": node.type})
            for child in node.children:
                _walk(child)

        _walk(tree.root_node)
        return comments
    except Exception as exc:
        logger.warning("tree-sitter parsing failed: %s", exc)
        return _extract_comments_regex(diff)


def _extract_comments_regex(diff: str) -> list[dict]:
    """Fallback: extract comments using regex."""
    comments = []
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            stripped = line[1:].strip()
            # Single-line comments (Python #, JS/TS/Go/Java/Rust //)
            for pattern in [r"//\s*(.+)", r"#\s*(.+)"]:
                match = re.search(pattern, stripped)
                if match:
                    comments.append({"text": match.group(1), "type": "regex_comment"})
                    break
            # Block comments (Java/Rust /* */)
            if not comments or comments[-1]["type"] != "regex_comment":
                for pattern in [r"/\*\s*(.+?)\s*\*/", r"///\s*(.+)"]:
                    match = re.search(pattern, stripped)
                    if match:
                        comments.append({"text": match.group(1), "type": "regex_comment"})
                        break
    return comments


def _extract_code_identifiers(diff: str) -> set[str]:
    """Extract identifiers from code lines in the diff."""
    identifiers = set()
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            # Find function/class/variable names across all supported languages
            for pattern in [
                r"def\s+(\w+)",           # Python
                r"class\s+(\w+)",         # Python/Java/Rust
                r"function\s+(\w+)",      # JS
                r"const\s+(\w+)",         # JS/TS
                r"let\s+(?:mut\s+)?(\w+)", # Rust/TS
                r"var\s+(\w+)",           # JS/Go
                r"(?:public|private|protected)\s+\w+\s+(\w+)",  # Java
                r"func\s+(?:\(\w+\s+\*?\w*\)\s+)?(\w+)",  # Go methods
                r"fn\s+(\w+)",            # Rust
                r"(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*(\w+)",  # JS async/generator
                r"type\s+(\w+)",          # TS/Go
                r"interface\s+(\w+)",     # TS/Java
                r"struct\s+(\w+)",        # Go/Rust
                r"enum\s+(\w+)",          # TS/Rust/Go
                r"impl\s+(?:<[^>]+>\s+)?(\w+)",  # Rust
                r"(?:interface|class)\s+(\w+)",  # Java/TS
            ]:
                for match in re.finditer(pattern, line):
                    identifiers.add(match.group(1).lower())
    return identifiers


def code_comment_intelligence_ast(
    diff: str,
    comment_text: str = "",
) -> tuple[float, list[dict]]:
    """Score code comment intelligence using AST parsing.

    Returns (score, details) where score ∈ [0, 1] (higher = smarter comments).
    Comments that explain business logic score higher than those that restate code.

    Falls back to regex-based scoring when tree-sitter is unavailable.
    """
    _load_parsers()

    # Extract comments via AST or regex
    ast_comments = _extract_comments_ast(diff)
    if not ast_comments:
        # No comments found in diff; use provided comment_text if any
        if comment_text:
            return _score_comment_text(comment_text, diff)
        return 0.5, [{"reason": "No code comments found in diff"}]

    # Extract identifiers from code
    code_identifiers = _extract_code_identifiers(diff)

    # Score each comment
    comment_scores = []
    details = []

    for comment_info in ast_comments:
        text = comment_info["text"]
        tokens = set(re.findall(r"[a-z]+", text.lower()))

        # Check if comment restates identifiers
        identifier_hits = tokens & code_identifiers
        identifier_ratio = len(identifier_hits) / max(len(tokens), 1)

        # Check for business/domain language
        business_words = re.findall(
            r"\b(because|ensure|prevent|avoid|customer|user|billing|security|"
            r"performance|constraint|requirement|spec|bug|edge.?case|TODO|"
            r"FIXME|HACK|workaround|note|important|critical)\b",
            text, re.I,
        )

        # Check for reasoning language
        reasoning_words = re.findall(
            r"\b(because|so that|therefore|reason|goal|avoid|prevent|ensure)\b",
            text, re.I,
        )

        # Score: penalize identifier restatement, reward business/reasoning language
        score = max(0.0, min(1.0,
            0.4
            + len(business_words) * 0.08
            + len(reasoning_words) * 0.1
            - identifier_ratio * 0.4
        ))

        comment_scores.append(score)
        details.append({
            "text": text[:100],
            "score": round(score, 3),
            "identifier_overlap": round(identifier_ratio, 2),
            "business_words": len(business_words),
            "reasoning_words": len(reasoning_words),
        })

    avg_score = sum(comment_scores) / len(comment_scores) if comment_scores else 0.5
    return round(avg_score, 3), details


def _score_comment_text(comment_text: str, diff: str) -> tuple[float, list[dict]]:
    """Score comment text when AST parsing is not available."""
    from slopguard.detectors.domains import overlap_score

    code_lines = [
        line[1:].strip()
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    code_text = " ".join(code_lines)

    if not code_text or not comment_text:
        return 0.5, []

    # Check overlap between comments and code
    divergence = 1.0 - overlap_score(comment_text, code_text)

    # Check for business language in comments
    business_words = len(re.findall(
        r"\b(because|ensure|prevent|avoid|customer|user|billing|security|"
        r"performance|constraint|requirement)\b",
        comment_text, re.I,
    ))

    score = max(0.0, min(1.0, divergence * 0.6 + business_words * 0.06 + 0.2))
    return round(score, 3), [{"reason": f"Divergence={divergence:.2f}, business_words={business_words}"}]
