import re
from collections import Counter

from slopguard.detectors.universal import clamp, split_sentences, tokenize
from slopguard.models import Domain, SignalResult


def overlap_score(a: str, b: str) -> float:
    a_tokens = {t for t in tokenize(a) if len(t) > 3}
    b_tokens = {t for t in tokenize(b) if len(t) > 3}
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens)


def _char_trigrams(text: str) -> set[str]:
    """Return the set of character-level trigrams for structural matching."""
    lower = text.lower()
    return {lower[i : i + 3] for i in range(max(0, len(lower) - 2))}


def _trigram_similarity(a: str, b: str) -> float:
    """Character-level trigram Jaccard similarity."""
    a_tri = _char_trigrams(a)
    b_tri = _char_trigrams(b)
    if not a_tri or not b_tri:
        return 0.0
    return len(a_tri & b_tri) / len(a_tri | b_tri)


def code_review_signals(text: str, diff: str = "", comments: list[str] | None = None) -> list[SignalResult]:
    comments = comments or []
    signals: list[SignalResult] = []
    divergence = 1.0 - overlap_score(text, diff) if diff else 0.50
    signals.append(
        SignalResult(
            name="pr_diff_divergence",
            score=round(clamp(divergence), 3),
            weight=1.5,
            label="adds_context" if divergence >= 0.62 else "diff_restatement",
            reason="Compares PR description tokens against changed diff tokens.",
        )
    )

    # --- Improved reviewer_impact_proxy ---
    # Look for deeper engagement signals: questions, disagreements, code suggestions, alternatives
    engagement_patterns = [
        r"\?",                                          # questions
        r"\b(because|risk|tradeoff|why|concern)\b",     # reasoning
        r"\b(instead|alternatively|what about|consider)\b",  # alternatives
        r"\b(suggest|nit|nitpick|disagree|but|however)\b",   # disagreements
        r"```",                                         # code suggestions
        r"\b(lgtm|approve|reject|request changes)\b",  # review actions
    ]
    engagement_hits = 0
    for comment in comments:
        for pattern in engagement_patterns:
            if re.search(pattern, comment, re.I):
                engagement_hits += 1
                break
    impact = min(1.0, engagement_hits / max(len(comments), 3)) if comments else 0.0
    # Bonus for diversity of engagement types
    if comments:
        type_count = sum(
            1 for pattern in engagement_patterns
            if any(re.search(pattern, c, re.I) for c in comments)
        )
        impact = min(1.0, impact + type_count * 0.05)
    signals.append(
        SignalResult(
            name="reviewer_impact_proxy",
            score=round(impact if comments else 0.40, 3),
            weight=0.9,
            label="active_review" if impact >= 0.6 else "rubber_stamp_risk",
            reason="Looks for review comments that ask questions, suggest alternatives, or force reasoning.",
        )
    )

    # --- Production: Tree-sitter AST-based code comment intelligence ---
    code_lines = [line for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")]
    if diff and code_lines:
        try:
            from slopguard.adapters.treesitter_comments import code_comment_intelligence_ast
            ast_score, ast_details = code_comment_intelligence_ast(diff)
            ast_available = any("tree-sitter not installed" not in d.get("reason", "") for d in ast_details) if ast_details else False
        except ImportError:
            ast_score = None
            ast_available = False

        if ast_available and ast_score is not None:
            intelligence = ast_score
            signals.append(
                SignalResult(
                    name="code_comment_intelligence",
                    score=round(clamp(intelligence), 3),
                    weight=1.0,
                    label="explains_why" if intelligence >= 0.6 else "restates_code",
                    reason="AST-based analysis: comments explain business logic vs restating code structure.",
                )
            )
        else:
            # Deterministic fallback: regex-based comment extraction
            code_comments = re.findall(r"//.+|# .+|/\*.+?\*/", diff, re.S)
            if code_comments and code_lines:
                comment_text = " ".join(code_comments)
                code_text = " ".join(code_lines)
                base_intelligence = 1.0 - overlap_score(comment_text, code_text)
                identifiers = set(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b", code_text))
                comment_tokens = set(tokenize(comment_text))
                identifier_overlap = len(comment_tokens & {i.lower() for i in identifiers}) / max(len(comment_tokens), 1)
                business_words = len(re.findall(
                    r"\b(because|ensure|prevent|avoid|customer|user|billing|security|performance|constraint|requirement|spec|bug|edge case)\b",
                    comment_text, re.I
                ))
                intelligence = clamp(base_intelligence - identifier_overlap * 0.3 + business_words * 0.06)
                signals.append(
                    SignalResult(
                        name="code_comment_intelligence",
                        score=round(clamp(intelligence), 3),
                        weight=1.0,
                        label="explains_why" if intelligence >= 0.6 else "restates_code",
                        reason="Regex-based analysis: checks if comments explain business logic vs restating identifiers.",
                    )
                )

    commit_reasoning = len(re.findall(r"\b(because|why|risk|avoid|prevent|tradeoff|root cause|fix(ing)?|resolve|trigger(ed)?|reported|cancel(ling)?|free|pending|without|before|after|when|exposure|vulnerability|leak|sanitiz|rotat|secret|token|credential|inject|exploit|patch|mitigat|CVE)\b", text, re.I))
    commit_actions = len(re.findall(r"\b(add|added|change|changed|refactor)\b", text, re.I))
    # Em-dash in PR descriptions signals reasoning context
    em_dash_bonus = 1 if re.search(r"[—–]", text) else 0
    ratio = clamp((commit_reasoning + em_dash_bonus + 0.5) / (commit_reasoning + em_dash_bonus + commit_actions + 2))
    signals.append(
        SignalResult(
            name="commit_reasoning_ratio",
            score=round(ratio, 3),
            weight=0.8,
            label="reasoned_commit" if ratio >= 0.55 else "action_only_commit",
            reason="Checks whether commit/PR language explains why, not just what changed.",
        )
    )

    # --- New: slop_velocity_proxy ---
    # Analyze the text for signals of degrading quality over time
    velocity_markers = re.findall(
        r"\b(rush|rushed|hotfix|hot-fix|quick fix|quickfix|temp|temporary|TODO|HACK|workaround|work-around|"
        r"band-?aid|kludge|duct.?tape|skip.?test|disable.?lint|wip|placeholder|stub)\b",
        text + " " + diff, re.I
    )
    velocity_score = clamp(0.60 - len(velocity_markers) * 0.12)
    signals.append(
        SignalResult(
            name="slop_velocity_proxy",
            score=round(velocity_score, 3),
            weight=1.1,
            label="deliberate_pace" if velocity_score >= 0.65 else "velocity_pressure",
            reason=f"Found {len(velocity_markers)} rush/shortcut markers suggesting quality pressure.",
        )
    )

    return signals


def docs_signals(text: str) -> list[SignalResult]:
    headings = len(re.findall(r"^#{1,6}\s+", text, re.M))
    tokens = len(tokenize(text))
    examples = len(re.findall(r"```|`[^`]+`|\bfor example\b|\be\.g\.\b|\bstep \d+\b", text, re.I))
    heading_score = clamp(1 - (headings * 35 / max(tokens, 1)))
    example_score = clamp(examples / max(headings, 1))

    # --- Production: NetworkX graph-based circularity detection ---
    try:
        from slopguard.adapters.networkx_circularity import circularity_graph_score
        nx_score, nx_details = circularity_graph_score(text)
        nx_available = len(nx_details) == 0 or "networkx not installed" not in nx_details[0].get("reason", "")
    except ImportError:
        nx_score = None
        nx_available = False

    if nx_available and nx_score is not None:
        circularity_score = nx_score
        circularity_detail = f"NetworkX graph analysis detected circular references."
    else:
        # Deterministic fallback: detect circular/repetitive explanations
        sentences = split_sentences(text)
        circular_windows = 0
        total_windows = max(len(sentences) - 2, 1)
        for i in range(len(sentences) - 2):
            window = sentences[i : i + 3]
            entity_sets = [{t for t in tokenize(s) if len(t) > 3} for s in window]
            if len(entity_sets) >= 3:
                prior_entities = entity_sets[0] | entity_sets[1]
                new_entities = entity_sets[2] - prior_entities
                if prior_entities:
                    first_third_overlap = len(entity_sets[0] & entity_sets[2]) / max(len(entity_sets[0] | entity_sets[2]), 1)
                else:
                    first_third_overlap = 0.0
                if len(new_entities) <= 1 and first_third_overlap > 0.5:
                    circular_windows += 1

        # Additional check: detect word-family repetition (e.g., "Authentication" → "authenticating" → "authenticate")
        lower = text.lower()
        word_family_score = 0.0

        # Find words that appear in multiple morphological forms
        # Strategy: extract 6+ char substrings and check if they appear in different word forms
        all_words = tokenize(lower)
        long_words = [w for w in all_words if len(w) >= 6]

        # Group words by their first 6 characters (common prefix = likely same root)
        prefix_groups: dict[str, set[str]] = {}
        for w in long_words:
            prefix = w[:6]
            prefix_groups.setdefault(prefix, set()).add(w)

        # Find groups with 3+ different word forms
        repeated_families = {prefix: forms for prefix, forms in prefix_groups.items() if len(forms) >= 3}
        if repeated_families:
            total_words = len(all_words)
            repeated_words = set()
            for forms in repeated_families.values():
                repeated_words.update(forms)
            repetition_count = len([w for w in all_words if w in repeated_words])
            repetition_ratio = repetition_count / max(total_words, 1)
            word_family_score = min(repetition_ratio * 2.0, 0.85)

        circularity_score = clamp(1 - (circular_windows / total_windows) - word_family_score)
        circularity_detail = f"Sliding window detected {circular_windows} circular entity patterns, word-family repetition: {word_family_score:.2f}."

    signals = [
        SignalResult(
            name="heading_to_content_ratio",
            score=round(heading_score, 3),
            weight=1.0,
            label="substantive" if heading_score >= 0.65 else "outline_heavy",
            reason="Penalizes docs with many headings and little substance under them.",
        ),
        SignalResult(
            name="concrete_example_density",
            score=round(example_score, 3),
            weight=1.1,
            label="example_rich" if example_score >= 0.45 else "example_poor",
            reason="Counts code snippets, examples, and step-style instructions.",
        ),
        SignalResult(
            name="circular_explanation_graph",
            score=round(circularity_score, 3),
            weight=1.5,
            label="adds_new_information" if circularity_score >= 0.7 else "circular_explanation",
            reason="Uses 3-sentence sliding windows to detect repeated entity sets without new information.",
        ),
    ]

    # --- New: codebase_drift_proxy ---
    # Detect staleness signals like outdated version numbers, deprecated API references, etc.
    staleness_markers = re.findall(
        r"\b(coming soon|to be determined|TBD|TBA|deprecated|obsolete|no longer supported|"
        r"will be removed|planned for|in a future release|end of life|EOL|sunset)\b",
        text, re.I
    )
    # Detect old year references (before current year - 2)
    year_refs = re.findall(r"\b(20[0-1]\d|202[0-3])\b", text)
    # Detect version patterns that look outdated
    old_version_hints = re.findall(r"\bv?[0-1]\.\d+\.\d+\b", text)
    # Detect placeholder/stub markers
    placeholder_markers = re.findall(r"\b(placeholder|TODO|FIXME|XXX|CHANGEME|insert .+ here)\b", text, re.I)

    drift_count = len(staleness_markers) + len(year_refs) * 0.5 + len(old_version_hints) * 0.3 + len(placeholder_markers)
    drift_score = clamp(1.0 - drift_count * 0.1)
    signals.append(
        SignalResult(
            name="codebase_drift_proxy",
            score=round(drift_score, 3),
            weight=0.9,
            label="current" if drift_score >= 0.65 else "stale_content_risk",
            reason=f"Found {len(staleness_markers)} staleness markers, {len(year_refs)} old year refs, {len(placeholder_markers)} placeholders.",
        )
    )

    return signals


def hiring_signals(text: str) -> list[SignalResult]:
    # --- Improved company_and_achievement_specificity ---
    company_refs = len(re.findall(r"\b(company|team|role|mission|product|customers|users)\b", text, re.I))
    quantified = len(re.findall(r"\b\d+%?\b|\b\d+x\b|\b\d+\+\b", text, re.I))
    # Penalize resume padding words
    padding_words = len(re.findall(
        r"\b(dynamic|synergy|leverage|spearheaded|facilitated|utilized|innovative|strategic|"
        r"proactive|self-starter|go-getter|team player|results-driven|detail-oriented|"
        r"fast-paced|passionate|motivated|hardworking)\b",
        text, re.I
    ))
    # Look for specific metrics/numbers
    specific_metrics = len(re.findall(r"\b\d+%|\$\d+[KkMmBb]?|\d+\s*(users|customers|requests|transactions|rps|qps)\b", text, re.I))
    # Look for company-specific product names (CamelCase, proper nouns not common words)
    product_names = len(re.findall(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b", text))
    score = clamp((company_refs * 0.08) + (quantified * 0.12) + (specific_metrics * 0.15) + (product_names * 0.06) - (padding_words * 0.07))

    role_specific = len(re.findall(r"\b(api|backend|frontend|flutter|react|node|python|aws|kubernetes|etl|pipeline|latency|revenue|users)\b", text, re.I))
    template_markers = len(re.findall(r"\b(excited to apply|great fit|passion|dedication|enthusiasm|your company|excited about the opportunity|bring my experience|strong interest)\b", text, re.I))
    template_score = clamp(0.55 + role_specific * 0.06 - template_markers * 0.15)

    signals = [
        SignalResult(
            name="company_and_achievement_specificity",
            score=round(score, 3),
            weight=1.0,
            label="specific" if score >= 0.5 else "generic_application",
            reason=f"Rewards company-specific references and quantified achievements; penalized {padding_words} padding words.",
        ),
        SignalResult(
            name="structural_template_detection",
            score=round(template_score, 3),
            weight=1.2,
            label="candidate_specific" if template_score >= 0.55 else "templated_application",
            reason="Penalizes common cover-letter templates and rewards role-specific evidence.",
        ),
    ]

    # --- New: batch_structural_fingerprint ---
    # Detect common AI cover letter structures
    sentences = split_sentences(text)
    ai_cover_patterns = 0
    if sentences:
        first = sentences[0].lower()
        last = sentences[-1].lower() if len(sentences) > 1 else ""
        # Classic AI intro
        if re.search(r"\b(i am writing to express my interest|i am excited to apply|dear hiring manager)\b", first, re.I):
            ai_cover_patterns += 2
        # Classic AI conclusion
        if re.search(r"\b(i look forward to|thank you for (your |considering)|i would welcome the opportunity|i am excited about)\b", last, re.I):
            ai_cover_patterns += 2
        # Intro-experience-conclusion 3-paragraph structure
        if 3 <= len(sentences) <= 8:
            # Check for the classic sandwich structure
            has_intro = bool(re.search(r"\b(i am|my name|applying for|position of)\b", first, re.I))
            has_skills_mid = any(re.search(r"\b(experience|skill|proficien|knowledge|expertise|years)\b", s, re.I) for s in sentences[1:-1]) if len(sentences) > 2 else False
            has_conclusion = bool(re.search(r"\b(look forward|thank|eager|opportunity|interview|excited|bring my)\b", last, re.I))
            if has_intro and has_skills_mid and has_conclusion:
                ai_cover_patterns += 3
    # Check for overly parallel sentence starts
    if len(sentences) >= 3:
        openers = [" ".join(tokenize(s)[:2]) for s in sentences if tokenize(s)]
        opener_counter = Counter(openers)
        max_repeat = max(opener_counter.values()) if opener_counter else 0
        if max_repeat >= 3:
            ai_cover_patterns += 1

    batch_fp_score = clamp(1.0 - ai_cover_patterns * 0.18)
    signals.append(
        SignalResult(
            name="batch_structural_fingerprint",
            score=round(batch_fp_score, 3),
            weight=1.8,
            label="organic_structure" if batch_fp_score >= 0.6 else "ai_cover_letter_pattern",
            reason=f"Detected {ai_cover_patterns} AI cover letter structural patterns.",
        )
    )

    return signals


def communications_signals(text: str) -> list[SignalResult]:
    action_hits = len(re.findall(r"\b(owner|deadline|by friday|next step|decision|action item|blocked|ship|approve)\b", text, re.I))
    sentences = max(1, len(split_sentences(text)))
    score = clamp(action_hits / sentences)
    words = tokenize(text)
    compression_score = clamp(1 - ((len(words) - action_hits * 9) / max(len(words), 1)) * 0.55)

    signals = [
        SignalResult(
            name="decision_action_density",
            score=round(score, 3),
            weight=1.2,
            label="actionable" if score >= 0.45 else "inflated_comms",
            reason="Checks whether communication contains decisions, owners, blockers, or next actions.",
        ),
        SignalResult(
            name="compression_score",
            score=round(compression_score, 3),
            weight=1.0,
            label="compact" if compression_score >= 0.55 else "overexpanded",
            reason="Estimates how much of the message could be compressed without losing decisions or actions.",
        ),
    ]

    # --- New: reply_information_score ---
    # Detect if reply adds info or just acknowledges
    low_info_patterns = re.findall(
        r"\b(sounds good|thanks|noted|will do|got it|makes sense|agreed|okay|ok|sure|"
        r"perfect|great|awesome|cool|nice|no worries|all good|roger|copy that|ack|"
        r"thumbs up|right|yep|yup|yes|exactly|absolutely|totally|definitely)\b",
        text, re.I
    )
    total_sentences = max(1, len(split_sentences(text)))
    low_info_ratio = len(low_info_patterns) / total_sentences
    reply_score = clamp(1.0 - low_info_ratio * 0.7)
    # If the reply is very short and mostly acknowledgement, penalize further
    if len(words) < 10 and low_info_ratio > 0.5:
        reply_score = clamp(reply_score - 0.2)
    signals.append(
        SignalResult(
            name="reply_information_score",
            score=round(reply_score, 3),
            weight=0.8,
            label="informative_reply" if reply_score >= 0.6 else "low_info_reply",
            reason=f"Found {len(low_info_patterns)} acknowledgement-only patterns in {total_sentences} sentences.",
        )
    )

    # --- New: meeting_notes_substance ---
    # Look for action items, owners, deadlines vs pure discussion summary
    action_items = len(re.findall(r"\b(action item|AI:|TODO|task|assigned to|owner:|responsible|follow.?up)\b", text, re.I))
    owner_refs = len(re.findall(r"\b(@\w+|assigned to \w+|\w+ will\b|\w+ to do\b)\b", text, re.I))
    deadline_refs = len(re.findall(r"\b(by \w+day|due|deadline|EOD|EOW|end of|before|target date|ETA)\b", text, re.I))
    discussion_markers = len(re.findall(r"\b(discussed|talked about|mentioned|brought up|conversation about|debate)\b", text, re.I))

    substance_hits = action_items + owner_refs + deadline_refs
    meeting_score = clamp((substance_hits * 0.15) + 0.3 - (discussion_markers * 0.06))
    signals.append(
        SignalResult(
            name="meeting_notes_substance",
            score=round(meeting_score, 3),
            weight=0.9,
            label="actionable_notes" if meeting_score >= 0.55 else "discussion_summary_only",
            reason=f"Found {action_items} action items, {owner_refs} owner refs, {deadline_refs} deadlines, {discussion_markers} pure discussion markers.",
        )
    )

    return signals


def content_signals(text: str) -> list[SignalResult]:
    # --- Improved claim_specificity ---
    # Look for weasel words without citations
    claims = len(re.findall(r"\b(should|must|best|proven|research shows|studies show|always|never)\b", text, re.I))
    weasel_words = len(re.findall(
        r"\b(many experts|some people|it is widely believed|research suggests|studies suggest|"
        r"experts say|most people|some argue|it is thought|it has been said|"
        r"according to experts|leading authorities)\b",
        text, re.I
    ))
    evidence = len(re.findall(r"\b(source|study|data|according to|measured|benchmark|example|case study)\b", text, re.I))
    # Check for actual citations near claims
    citation_patterns = len(re.findall(r"\[\d+\]|\([A-Z][a-z]+,?\s*\d{4}\)|doi:|https?://", text))
    unsupported_ratio = (claims + weasel_words) / max(claims + weasel_words + evidence + citation_patterns, 1)
    score = clamp(1 - unsupported_ratio)

    words = max(len(tokenize(text)), 1)
    specifics = len(re.findall(r"\b\d+%?|\b[A-Z][A-Za-z]+/[A-Z][A-Za-z]+|\bbenchmark|dataset|case study|measured\b", text))
    time_to_value = clamp((specifics * 18 + evidence * 10) / words)
    structure_rehash = 1 - clamp(len(re.findall(r"\b(introduction|conclusion|ultimate guide|best practices|key benefits)\b", text, re.I)) * 0.18)

    signals = [
        SignalResult(
            name="claim_specificity",
            score=round(score, 3),
            weight=1.2,
            label="supported" if score >= 0.55 else "unsupported_claims",
            reason=f"Found {claims} broad claims, {weasel_words} weasel phrases, {evidence} evidence cues, {citation_patterns} citations.",
        ),
        SignalResult(
            name="time_to_value_ratio",
            score=round(time_to_value, 3),
            weight=1.0,
            label="high_payoff" if time_to_value >= 0.3 else "low_payoff",
            reason="Compares concrete facts and evidence cues against reading length.",
        ),
        SignalResult(
            name="structure_rehash",
            score=round(clamp(structure_rehash), 3),
            weight=0.8,
            label="fresh_structure" if structure_rehash >= 0.65 else "seo_template",
            reason="Detects common SEO article scaffolding and repeated template sections.",
        ),
    ]

    # --- New: originality_proxy ---
    # Check for unique phrasing, specific examples, original data
    sentences = split_sentences(text)
    unique_phrases = 0
    generic_phrases = 0
    for sentence in sentences:
        stokens = tokenize(sentence)
        # Unique: contains proper nouns, specific numbers, or rare word combos
        has_specifics = bool(re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", sentence))  # proper noun sequences
        has_data = bool(re.search(r"\b\d+(\.\d+)?(%|\s*(ms|kb|mb|gb|users|rps|tps|dollars|euros))\b", sentence, re.I))
        has_quote = bool(re.search(r'"[^"]{10,}"', sentence))
        if has_specifics or has_data or has_quote:
            unique_phrases += 1
        # Generic: common filler openings
        elif re.search(r"^(in today's|it is important|this (article|guide|post)|when it comes to|there are many)", sentence.strip(), re.I):
            generic_phrases += 1
    originality = clamp((unique_phrases * 0.2 + 0.4) - generic_phrases * 0.12) if sentences else 0.4
    signals.append(
        SignalResult(
            name="originality_proxy",
            score=round(originality, 3),
            weight=0.9,
            label="original_voice" if originality >= 0.55 else "generic_content",
            reason=f"Found {unique_phrases} sentences with original data/examples, {generic_phrases} generic filler openings.",
        )
    )

    return signals


def academia_signals(text: str) -> list[SignalResult]:
    citations = len(re.findall(r"\[[0-9,\s]+\]|\([A-Z][A-Za-z]+,\s*20\d{2}\)|doi:", text, re.I))
    hedges = len(re.findall(r"\b(may|might|suggests|limitations|future work|confidence interval|p-value)\b", text, re.I))
    score = clamp((citations * 0.09) + (hedges * 0.08))

    # --- Improved stylistic_consistency ---
    # Use 250-char windows and track multiple features per window
    windows = [text[i : i + 250] for i in range(0, len(text), 250) if text[i : i + 250].strip()]
    if len(windows) < 2:
        style_score = 1.0
    else:
        window_features: list[tuple[float, float, float]] = []
        for window in windows:
            w_tokens = tokenize(window)
            w_sentences = split_sentences(window)
            if w_tokens:
                avg_word_len = sum(len(t) for t in w_tokens) / len(w_tokens)
                avg_sent_len = len(w_tokens) / max(len(w_sentences), 1)
                vocab_density = len(set(w_tokens)) / len(w_tokens)
                window_features.append((avg_word_len, avg_sent_len, vocab_density))
        if len(window_features) < 2:
            style_score = 1.0
        else:
            # Compute consistency across all three feature dimensions
            feature_drifts = []
            for dim in range(3):
                values = [f[dim] for f in window_features]
                max_val = max(values)
                min_val = min(values)
                mean_val = sum(values) / len(values)
                if mean_val > 0:
                    feature_drifts.append((max_val - min_val) / mean_val)
                else:
                    feature_drifts.append(0.0)
            avg_drift = sum(feature_drifts) / len(feature_drifts)
            style_score = clamp(1 - avg_drift * 0.8)

    self_refs = len(re.findall(r"\b(our previous work|we previously|as we showed)\b", text, re.I))
    self_score = clamp(1 - self_refs * 0.12)

    signals = [
        SignalResult(
            name="academic_grounding",
            score=round(score, 3),
            weight=1.1,
            label="grounded" if score >= 0.5 else "ungrounded_academic_style",
            reason="Looks for citations, limitations, statistical language, and cautious claims.",
        ),
        SignalResult(
            name="stylistic_consistency",
            score=round(style_score, 3),
            weight=0.9,
            label="consistent" if style_score >= 0.7 else "style_shift",
            reason="Uses 250-char sliding windows tracking word length, sentence length, and vocabulary density.",
        ),
        SignalResult(
            name="self_citation_inflation",
            score=round(self_score, 3),
            weight=0.7,
            label="normal_self_reference" if self_score >= 0.7 else "self_reference_heavy",
            reason="Flags repeated self-reference patterns for human review.",
        ),
    ]

    # --- New: citation_claim_alignment ---
    # Check if text around citations uses verification language vs vague references
    citation_spans = list(re.finditer(r"\[[0-9,\s]+\]|\([A-Z][A-Za-z]+,\s*20\d{2}\)", text))
    if citation_spans:
        verification_verbs = 0
        vague_verbs = 0
        for match in citation_spans:
            start = max(0, match.start() - 80)
            end = min(len(text), match.end() + 30)
            context = text[start:end].lower()
            if re.search(r"\b(demonstrated|showed|found|confirmed|established|proved|measured|observed|reported|identified)\b", context):
                verification_verbs += 1
            elif re.search(r"\b(discussed|mentioned|noted|described|addressed|touched on|referred|related)\b", context):
                vague_verbs += 1
        total_cite_verbs = max(verification_verbs + vague_verbs, 1)
        alignment = clamp(0.4 + (verification_verbs / total_cite_verbs) * 0.5)
    else:
        alignment = 0.4  # No citations found
    signals.append(
        SignalResult(
            name="citation_claim_alignment",
            score=round(alignment, 3),
            weight=0.8,
            label="verified_citations" if alignment >= 0.6 else "vague_references",
            reason=f"Of {len(citation_spans)} citations, context uses {verification_verbs if citation_spans else 0} verification verbs vs {vague_verbs if citation_spans else 0} vague verbs.",
        )
    )

    return signals


def marketplace_signals(text: str) -> list[SignalResult]:
    # --- Improved review_specificity ---
    # Expanded product-specific keyword list with category-specific details
    product_specific = len(re.findall(
        r"\b(size|fit|battery|screen|fabric|shipping|packaging|model|serial|warranty|washed|charged|"
        r"color|weight|dimensions|material|texture|smell|taste|ingredient|recipe|assembly|instructions|"
        r"compatibility|firmware|update|version|adapter|cable|plug|brightness|resolution|speed|"
        r"durability|stitching|zipper|button|pocket|sole|heel|cushion|support|comfort|noise|"
        r"installation|setup|manual|customer service|replacement|exchange|"
        r"port|hub|monitor|reader|keyboard|mouse|display|audio|video|bluetooth|wifi|usb|"
        r"charging|heat|warm|cool|fan|therm(al)?|build.?quality|performance|lag|latency)\b",
        text, re.I
    ))
    generic_praise = len(re.findall(r"\b(amazing|excellent|highly recommend|great product|must buy|perfect)\b", text, re.I))
    # Category-specific detail bonus
    category_details = len(re.findall(
        r"\b(thread count|lumens|watts|megapixel|mAh|RPM|decibel|fluid ounce|cubic|gallon|"
        r"pound|ounce|inch|centimeter|millimeter|gram|kilogram|"
        r"Hz|kHz|MHz|GB|TB|MB|KB|fps|Mbps|Gbps|ns|ms|sec|minutes?|hours?|days?)\b",
        text, re.I
    ))
    score = clamp((product_specific * 0.12) + (category_details * 0.15) - (generic_praise * 0.08) + 0.35)

    temporal_markers = len(re.findall(r"\b(day|week|month|after|before|arrived|delivered|returned|refund)\b", text, re.I))
    authenticity = clamp(0.35 + product_specific * 0.1 + temporal_markers * 0.08 + category_details * 0.1 - generic_praise * 0.08)

    signals = [
        SignalResult(
            name="review_specificity",
            score=round(score, 3),
            weight=1.2,
            label="buyer_specific" if score >= 0.55 else "generic_review",
            reason="Rewards details only a real buyer is likely to mention, including category-specific measurements.",
        ),
        SignalResult(
            name="reviewer_history_authenticity_proxy",
            score=round(authenticity, 3),
            weight=1.0,
            label="experience_grounded" if authenticity >= 0.55 else "generic_review_pattern",
            reason="Uses product details and time/use markers as a local proxy for real buyer experience.",
        ),
    ]

    # --- New: temporal_clustering_proxy ---
    # Detect review text that lacks temporal specificity
    time_specifics = len(re.findall(
        r"\b(\d+\s*(day|week|month|year)s?|january|february|march|april|may|june|july|august|"
        r"september|october|november|december|last (week|month|year)|for \d+ (day|week|month)|"
        r"since \w+|after \d+|first \d+|been using)\b",
        text, re.I
    ))
    usage_context = len(re.findall(r"\b(bought|purchased|ordered|received|used it for|been using|owned)\b", text, re.I))
    temporal_score = clamp(0.3 + time_specifics * 0.15 + usage_context * 0.12)
    signals.append(
        SignalResult(
            name="temporal_clustering_proxy",
            score=round(temporal_score, 3),
            weight=0.9,
            label="time_grounded" if temporal_score >= 0.55 else "temporally_vague",
            reason=f"Found {time_specifics} temporal specifics and {usage_context} purchase/usage context markers.",
        )
    )

    # --- New: pros_cons_balance ---
    # Authentic reviews typically mention both positives and negatives
    pros = len(re.findall(r"\b(works\s*(fine|great|well)|good|decent|fine|fast|smooth|love|like|happy|pleased|recommend)\b", text, re.I))
    cons = len(re.findall(r"\b(slow|issue|problem|warm|hot|lag|break|broken|disappointing|wish|but|though|however|not\s+great)\b", text, re.I))
    total_opinions = pros + cons
    if total_opinions >= 2:
        # Balanced reviews (both pros and cons) score higher
        min_side = min(pros, cons)
        balance_score = clamp(0.4 + (min_side / max(total_opinions, 1)) * 0.6)
    else:
        balance_score = 0.35  # Too few opinions to judge
    signals.append(
        SignalResult(
            name="pros_cons_balance",
            score=round(balance_score, 3),
            weight=0.8,
            label="balanced_review" if balance_score >= 0.55 else "one_sided_review",
            reason=f"Found {pros} positive opinions and {cons} negative opinions.",
        )
    )

    return signals


def social_news_signals(text: str) -> list[SignalResult]:
    # --- Improved rage_bait_fingerprint ---
    # Expanded emotional trigger word list + capitalization abuse detection
    emotional = len(re.findall(
        r"\b(shocking|destroyed|outrage|you won't believe|exposed|terrifying|insane|"
        r"disgusting|unbelievable|horrifying|scandalous|explosive|bombshell|devastating|"
        r"infuriating|sickening|nightmare|catastrophe|betrayed|corrupt|rigged|scam|fraud)\b",
        text, re.I
    ))
    source_refs = len(re.findall(r"\b(source|according to|report|document|video|data|statement)\b", text, re.I))
    # Capitalization abuse: count words that are ALL CAPS (3+ letters, excluding common acronyms)
    common_acronyms = {"USA", "UK", "EU", "FBI", "CIA", "NASA", "CEO", "CTO", "API", "URL", "HTTP", "HTML", "CSS", "PDF", "FAQ"}
    all_caps_words = [w for w in re.findall(r"\b[A-Z]{3,}\b", text) if w not in common_acronyms]
    caps_abuse = len(all_caps_words)
    # Excessive punctuation
    exclamation_abuse = len(re.findall(r"!{2,}|\?{2,}|!+\?+", text))

    score = clamp(0.55 + (source_refs * 0.1) - (emotional * 0.1) - (caps_abuse * 0.06) - (exclamation_abuse * 0.08))

    coordinated_markers = len(re.findall(r"\b(copy this|share everywhere|they don't want you to know|wake up|mainstream media)\b", text, re.I))
    coordination_score = clamp(0.65 + source_refs * 0.08 - coordinated_markers * 0.16)

    signals = [
        SignalResult(
            name="rage_bait_fingerprint",
            score=round(score, 3),
            weight=1.1,
            label="sourced" if score >= 0.6 else "engagement_bait_risk",
            reason=f"Balances {source_refs} sourcing cues against {emotional} rage words, {caps_abuse} ALL-CAPS abuse, {exclamation_abuse} punctuation abuse.",
        ),
        SignalResult(
            name="network_coordination_proxy",
            score=round(coordination_score, 3),
            weight=0.9,
            label="organic_language" if coordination_score >= 0.6 else "coordination_risk",
            reason="Flags copy-and-amplify phrasing often seen in coordinated posts.",
        ),
    ]

    # --- New: posting_cadence_proxy ---
    # Detect text patterns of automated posting (no personal voice, no typos, unnaturally polished)
    personal_voice = len(re.findall(r"\b(I think|I feel|IMO|IMHO|personally|in my experience|tbh|honestly|lol|haha)\b", text, re.I))
    informal_markers = len(re.findall(r"\b(gonna|wanna|gotta|kinda|sorta|idk|ngl|smh|fwiw|imo|btw)\b", text, re.I))
    # Contractions are a sign of natural writing
    contractions = len(re.findall(r"\b\w+'(t|re|ve|ll|d|s|m)\b", text, re.I))
    # Overly polished = no contractions + no informal markers + no personal voice in substantial text
    word_count = len(tokenize(text))
    if word_count > 20:
        naturalness = clamp(0.35 + personal_voice * 0.1 + informal_markers * 0.08 + contractions * 0.04)
    else:
        naturalness = 0.5  # Too short to judge
    signals.append(
        SignalResult(
            name="posting_cadence_proxy",
            score=round(naturalness, 3),
            weight=0.8,
            label="human_voice" if naturalness >= 0.55 else "automated_tone",
            reason=f"Found {personal_voice} personal voice markers, {informal_markers} informal markers, {contractions} contractions.",
        )
    )

    # --- New: engagement_authenticity_proxy ---
    # Detect text designed to maximize engagement
    cta_patterns = len(re.findall(
        r"\b(share this|like and subscribe|follow me|retweet|spread the word|tag a friend|"
        r"comment below|drop a|hit the|smash that|don't forget to|make sure to follow|"
        r"link in bio|check out my)\b",
        text, re.I
    ))
    outrage_triggers = len(re.findall(
        r"\b(prove me wrong|change my mind|let that sink in|think about that|"
        r"bet you didn't know|nobody is talking about|why is nobody|"
        r"am I the only one|unpopular opinion)\b",
        text, re.I
    ))
    engagement_manipulation = cta_patterns + outrage_triggers + emotional * 0.3
    engagement_score = clamp(0.7 - engagement_manipulation * 0.1)
    signals.append(
        SignalResult(
            name="engagement_authenticity_proxy",
            score=round(engagement_score, 3),
            weight=0.9,
            label="authentic_engagement" if engagement_score >= 0.55 else "engagement_farming",
            reason=f"Found {cta_patterns} calls-to-action, {outrage_triggers} outrage triggers.",
        )
    )

    return signals


def domain_signals(domain: Domain, text: str, metadata: dict | None = None) -> list[SignalResult]:
    metadata = metadata or {}
    if domain == "code_review":
        return code_review_signals(text, metadata.get("diff", ""), metadata.get("comments", []))
    if domain == "docs":
        return docs_signals(text)
    if domain == "hiring":
        return hiring_signals(text)
    if domain == "communications":
        return communications_signals(text)
    if domain == "content":
        return content_signals(text)
    if domain == "academia":
        return academia_signals(text)
    if domain == "marketplace":
        return marketplace_signals(text)
    if domain == "social_news":
        return social_news_signals(text)
    return []


def structural_fingerprint(text: str) -> tuple[int, ...]:
    return tuple(min(20, len(tokenize(sentence))) for sentence in split_sentences(text)[:8])


def batch_clusters(texts: list[str]) -> list[dict]:
    # --- 1. Structural fingerprint clustering ---
    fingerprints = [structural_fingerprint(text) for text in texts]
    buckets: dict[tuple[int, ...], list[int]] = {}
    for index, fingerprint in enumerate(fingerprints):
        buckets.setdefault(fingerprint, []).append(index)

    clusters = []
    for fingerprint, indexes in buckets.items():
        if len(indexes) > 1:
            clusters.append(
                {
                    "type": "structural_template",
                    "item_indexes": indexes,
                    "fingerprint": list(fingerprint),
                    "reason": "Items share the same sentence-length structure.",
                }
            )

    # --- 2. Opening repetition clustering ---
    opening_counter = Counter()
    openings: list[str] = []
    for text in texts:
        first = " ".join(tokenize(text)[:5])
        openings.append(first)
        opening_counter[first] += 1
    for opening, count in opening_counter.items():
        if opening and count > 1:
            clusters.append(
                {
                    "type": "repeated_opening",
                    "item_indexes": [i for i, value in enumerate(openings) if value == opening],
                    "opening": opening,
                    "reason": "Multiple items start with the same wording.",
                }
            )

    # --- 3. Production: FAISS + sentence-transformers embedding clustering ---
    # Uses deep semantic embeddings with IVF index for fast similarity search
    if len(texts) >= 2:
        faiss_results = _faiss_embedding_clusters(texts)
        if faiss_results:
            clusters.extend(faiss_results)
        else:
            # Fallback: TF-IDF + cosine similarity clustering
            tfidf_clusters = _tfidf_clusters(texts)
            clusters.extend(tfidf_clusters)

    return clusters


def _faiss_embedding_clusters(texts: list[str], threshold: float = 0.55) -> list[dict]:
    """Cluster texts using sentence-transformers embeddings + FAISS IVF index."""
    try:
        import numpy as np
        from slopguard.adapters.semantic_embedding import encode as emb_encode
        from slopguard.adapters.faiss_clustering import faiss_clusters
    except ImportError:
        return []

    embeddings = emb_encode(texts)
    if embeddings is None or len(embeddings) < 2:
        return []

    return faiss_clusters(embeddings, texts, threshold=threshold)


def _tfidf_clusters(texts: list[str], threshold: float = 0.60) -> list[dict]:
    """Cluster texts using TF-IDF vectorization and cosine similarity."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        # Fallback: use character-trigram similarity if scikit-learn unavailable
        return _trigram_fallback_clusters(texts)

    if len(texts) < 2:
        return []

    try:
        vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=5000,
            min_df=1,
            sublinear_tf=True,
            strip_accents="unicode",
        )
        tfidf_matrix = vectorizer.fit_transform(texts)
        sim_matrix = cosine_similarity(tfidf_matrix)

        # Greedy clustering: group items above threshold
        used: set[int] = set()
        clusters = []
        for left in range(len(texts)):
            if left in used:
                continue
            group = [left]
            for right in range(left + 1, len(texts)):
                if sim_matrix[left, right] >= threshold:
                    group.append(right)
            if len(group) > 1:
                used.update(group)
                clusters.append(
                    {
                        "type": "tfidf_similarity",
                        "item_indexes": group,
                        "similarity_score": round(
                            float(
                                sum(
                                    sim_matrix[a, b]
                                    for i, a in enumerate(group)
                                    for b in group[i + 1 :]
                                )
                                / max(len(group) * (len(group) - 1) // 2, 1)
                            ),
                            3,
                        ),
                        "reason": "Items share high TF-IDF cosine similarity (same-prompt paraphrase detection).",
                    }
                )
        return clusters
    except Exception:
        return _trigram_fallback_clusters(texts)


def _trigram_fallback_clusters(texts: list[str]) -> list[dict]:
    """Fallback clustering using character-level trigram Jaccard similarity."""
    token_sets = [{t for t in tokenize(text) if len(t) > 3} for text in texts]
    similar_indexes: list[list[int]] = []
    used: set[int] = set()
    for left in range(len(token_sets)):
        if left in used:
            continue
        group = [left]
        for right in range(left + 1, len(token_sets)):
            union = token_sets[left] | token_sets[right]
            word_jaccard = len(token_sets[left] & token_sets[right]) / len(union) if union else 0.0
            trigram_sim = _trigram_similarity(texts[left], texts[right])
            combined = word_jaccard * 0.5 + trigram_sim * 0.5
            if combined >= 0.45:
                group.append(right)
        if len(group) > 1:
            used.update(group)
            similar_indexes.append(group)

    clusters = []
    for group in similar_indexes:
        clusters.append(
            {
                "type": "semantic_similarity_proxy",
                "item_indexes": group,
                "reason": "Items share high token overlap and character-trigram structural similarity.",
            }
        )
    return clusters
