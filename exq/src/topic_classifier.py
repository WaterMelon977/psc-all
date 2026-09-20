import yaml
import re
from typing import List, Dict, Any, Tuple
from collections import OrderedDict

class TopicRule:
    def __init__(self, name: str, keywords: Dict[str, float], regex_rules: List[Tuple[re.Pattern, float]]):
        self.name = name
        self.keywords = keywords  # keyword -> weight
        self.regex_rules = regex_rules  # list of (compiled_pattern, weight)

class TopicClassifier:
    def __init__(self, yaml_path: str):
        self.yaml_path = yaml_path
        self.topics_order: List[str] = []
        self.topic_rules: List[TopicRule] = []
        self._load_config()

    def _load_config(self):
        with open(self.yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        raw_topics = data.get("topics", [])
        for item in raw_topics:
            if isinstance(item, str):
                # Topic without explicit keywords
                topic_name = item.strip()
                self.topics_order.append(topic_name)
                self.topic_rules.append(TopicRule(name=topic_name, keywords={}, regex_rules=[]))
            elif isinstance(item, dict):
                topic_name = item.get("name", "").strip()
                if not topic_name:
                    continue
                self.topics_order.append(topic_name)

                keywords_dict: Dict[str, float] = {}
                raw_kws = item.get("keywords", {})
                if isinstance(raw_kws, dict):
                    for k, w in raw_kws.items():
                        keywords_dict[str(k).lower().strip()] = float(w)
                elif isinstance(raw_kws, list):
                    for k in raw_kws:
                        keywords_dict[str(k).lower().strip()] = 1.0

                regex_rules: List[Tuple[re.Pattern, float]] = []
                raw_regex = item.get("regex", [])
                if isinstance(raw_regex, list):
                    for r_item in raw_regex:
                        if isinstance(r_item, dict):
                            pat_str = r_item.get("pattern", "")
                            w = float(r_item.get("weight", 1.0))
                            if pat_str:
                                try:
                                    compiled = re.compile(pat_str, re.IGNORECASE)
                                    regex_rules.append((compiled, w))
                                except re.error:
                                    pass
                        elif isinstance(r_item, str):
                            try:
                                compiled = re.compile(r_item, re.IGNORECASE)
                                regex_rules.append((compiled, 1.0))
                            except re.error:
                                pass

                self.topic_rules.append(TopicRule(
                    name=topic_name,
                    keywords=keywords_dict,
                    regex_rules=regex_rules
                ))

    def _normalize_text(self, text: str) -> str:
        # Lowercase, replace multiple whitespaces with single space
        return re.sub(r"\s+", " ", text.lower().strip())

    def classify(self, question_text: str, options: Dict[str, str]) -> Tuple[str, Dict[str, float]]:
        """
        Calculates scores for each topic based on question and option texts.
        Returns:
        - Winning topic (highest score, tie-broken by topics.yaml order)
        - Scores dict {topic_name: score}
        """
        combined_text = question_text + " " + " ".join(options.values())
        norm_text = self._normalize_text(combined_text)

        scores: Dict[str, float] = {t.name: 0.0 for t in self.topic_rules}

        for rule in self.topic_rules:
            topic_score = 0.0

            # 1. Keywords matching with word boundaries
            for kw, weight in rule.keywords.items():
                # Word boundary check for letters/numbers, literal for special chars
                if re.match(r"^\w+(?:\s+\w+)*$", kw):
                    pattern = rf"\b{re.escape(kw)}\b"
                else:
                    pattern = re.escape(kw)

                if re.search(pattern, norm_text, re.IGNORECASE):
                    topic_score += weight

            # 2. Regex matching
            for pattern, weight in rule.regex_rules:
                if pattern.search(norm_text):
                    topic_score += weight

            scores[rule.name] = topic_score

        # Select highest scoring topic
        # In case of tie, preserve order in topics.yaml
        best_topic = self.topics_order[0] if self.topics_order else "General"
        max_score = -1.0

        for rule in self.topic_rules:
            s = scores[rule.name]
            if s > max_score:
                max_score = s
                best_topic = rule.name

        return best_topic, scores
