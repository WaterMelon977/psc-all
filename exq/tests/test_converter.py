import unittest
import json
import tempfile
from pathlib import Path

from src.models import RawSpan, RawLine, RawQuestionBlock, ParsedOption, Question
from src.language_detector import LanguageDetector
from src.question_parser import QuestionParser
from src.answer_detector import AnswerDetector
from src.topic_classifier import TopicClassifier
from src.markdown_renderer import MarkdownRenderer
from src.json_renderer import JSONRenderer
from src.review_generator import ReviewGenerator

class TestConverter(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.yaml_file = Path(self.temp_dir.name) / "topics.yaml"
        yaml_content = """topics:
  - name: Strength of Materials
    keywords:
      stress: 5
      strain: 5
      bending moment: 10
    regex:
      - pattern: "\\bSFD\\b"
        weight: 10
  - name: Fluid Mechanics
    keywords:
      viscosity: 7
      bernoulli: 10
    regex:
      - pattern: "centrifugal\\\\s+pump"
        weight: 10
  - name: Thermodynamics
    keywords:
      entropy: 10
      enthalpy: 8
      carnot: 10
"""
        self.yaml_file.write_text(yaml_content, encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_1_normal_question(self):
        """Test 1: Normal question with 4 options and one green option."""
        options = [
            ParsedOption(number=1, text="First option", spans=[RawSpan("1. First option", 0xff0000, (0, 0, 10, 10))]),
            ParsedOption(number=2, text="Second option", spans=[RawSpan("2. Second option", 0x008000, (0, 0, 10, 10))]),
            ParsedOption(number=3, text="Third option", spans=[RawSpan("3. Third option", 0xff0000, (0, 0, 10, 10))]),
            ParsedOption(number=4, text="Fourth option", spans=[RawSpan("4. Fourth option", 0xff0000, (0, 0, 10, 10))]),
        ]
        detector = AnswerDetector()
        answers, issues = detector.detect_answers(options)
        self.assertEqual(answers, [2])
        self.assertEqual(len(issues), 0)

    def test_2_telugu_duplicate_filtering(self):
        """Test 2: Telugu duplicate is removed, English is retained."""
        eng_block = RawQuestionBlock(
            qnum=147,
            page_number=1,
            header_text="Question Number : 147",
            lines=[RawLine("What is the effect of stress?", [RawSpan("What is the effect of stress?", 0, (0, 0, 0, 0))], 1)]
        )
        tel_block = RawQuestionBlock(
            qnum=147,
            page_number=2,
            header_text="Question Number : 147",
            lines=[RawLine("ఒత్తిడి ప్రభావం ఏమిటి?", [RawSpan("ఒత్తిడి ప్రభావం ఏమిటి?", 0, (0, 0, 0, 0))], 2)]
        )

        detector = LanguageDetector()
        retained, discarded, anomalies = detector.filter_language([eng_block, tel_block])
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0].qnum, 147)
        self.assertIn("stress", retained[0].lines[0].text)
        self.assertEqual(discarded, 1)

    def test_3_multiple_green_options(self):
        """Test 3: Multiple green options are all retained."""
        options = [
            ParsedOption(number=1, text="First option", spans=[RawSpan("1. First option", 0xff0000, (0, 0, 10, 10))]),
            ParsedOption(number=2, text="Second option", spans=[RawSpan("2. Second option", 0x008000, (0, 0, 10, 10))]),
            ParsedOption(number=3, text="Third option", spans=[RawSpan("3. Third option", 0xff0000, (0, 0, 10, 10))]),
            ParsedOption(number=4, text="Fourth option", spans=[RawSpan("4. Fourth option", 0x008000, (0, 0, 10, 10))]),
        ]
        detector = AnswerDetector()
        answers, issues = detector.detect_answers(options)
        self.assertEqual(answers, [2, 4])
        self.assertTrue(any("Multiple green options" in issue for issue in issues))

    def test_4_no_green_option(self):
        """Test 4: Missing green option produces empty answer and flags review item."""
        options = [
            ParsedOption(number=1, text="First option", spans=[RawSpan("1. First option", 0, (0, 0, 10, 10))]),
            ParsedOption(number=2, text="Second option", spans=[RawSpan("2. Second option", 0, (0, 0, 10, 10))]),
        ]
        detector = AnswerDetector()
        answers, issues = detector.detect_answers(options)
        self.assertEqual(answers, [])
        self.assertTrue(any("Could not determine the correct answer" in issue for issue in issues))

    def test_5_english_only_question(self):
        """Test 5: An English-only question without Telugu pair is retained."""
        eng_block = RawQuestionBlock(
            qnum=5,
            page_number=1,
            header_text="Question Number : 5",
            lines=[RawLine("Standalone English question", [RawSpan("Standalone English question", 0, (0, 0, 0, 0))], 1)]
        )
        detector = LanguageDetector()
        retained, discarded, _ = detector.filter_language([eng_block])
        self.assertEqual(len(retained), 1)
        self.assertEqual(discarded, 0)

    def test_6_topic_keyword_match(self):
        """Test 6: Topic classifier keyword matching."""
        classifier = TopicClassifier(str(self.yaml_file))
        topic, scores = classifier.classify("What is the entropy of a closed system?", {"1": "zero", "2": "increases"})
        self.assertEqual(topic, "Thermodynamics")
        self.assertGreaterEqual(scores["Thermodynamics"], 10)

    def test_7_weighted_topic_conflict(self):
        """Test 7: Highly specific keyword beats multiple generic keywords."""
        conflict_file = Path(self.temp_dir.name) / "topics_conflict.yaml"
        conflict_file.write_text("""topics:
  - name: Topic Generic
    keywords:
      flow: 1
      rate: 1
      pipe: 1
  - name: Topic Specific
    keywords:
      bernoulli: 10
""", encoding="utf-8")
        classifier = TopicClassifier(str(conflict_file))
        topic, scores = classifier.classify("Calculate the flow rate in the pipe using Bernoulli equation.", {})
        self.assertEqual(topic, "Topic Specific")
        self.assertGreater(scores["Topic Specific"], scores["Topic Generic"])

    def test_8_regex_topic_match(self):
        """Test 8: Regular expression matching."""
        classifier = TopicClassifier(str(self.yaml_file))
        topic, scores = classifier.classify("The operation of a centrifugal    pump is analyzed.", {})
        self.assertEqual(topic, "Fluid Mechanics")
        self.assertGreaterEqual(scores["Fluid Mechanics"], 10)

    def test_9_output_consistency_json_markdown(self):
        """Test 9: JSON and Markdown representations are fully consistent."""
        q = Question(
            question_number=147,
            page_number=10,
            question_text="Which of the following statements is correct?",
            options={
                "1": "Option A",
                "2": "Option B",
                "3": "Option C",
                "4": "Option D"
            },
            answer=[4],
            topic="Thermodynamics"
        )

        classifier = TopicClassifier(str(self.yaml_file))
        md_renderer = MarkdownRenderer(classifier.topics_order)
        md_out = md_renderer.render([q])

        json_renderer = JSONRenderer()
        json_out = json_renderer.render([q])
        parsed_json = json.loads(json_out)

        # Check question number
        self.assertIn("## Question 147", md_out)
        self.assertEqual(parsed_json["questions"][0]["question_number"], 147)

        # Check options
        self.assertIn("4. Option D", md_out)
        self.assertEqual(parsed_json["questions"][0]["options"]["4"], "Option D")

        # Check answer
        self.assertIn("> **Answer: 4**", md_out)
        self.assertEqual(parsed_json["questions"][0]["answer"], [4])

        # Check topic
        self.assertIn("**Topic:** Thermodynamics", md_out)
        self.assertEqual(parsed_json["questions"][0]["topic"], "Thermodynamics")

    def test_10_topic_order_preservation(self):
        """Test 10: Topic order strictly matches YAML order."""
        classifier = TopicClassifier(str(self.yaml_file))
        self.assertEqual(classifier.topics_order, ["Strength of Materials", "Fluid Mechanics", "Thermodynamics"])

        q1 = Question(1, 1, "test", {}, [1], "Thermodynamics")
        q2 = Question(2, 1, "test", {}, [1], "Strength of Materials")

        md_renderer = MarkdownRenderer(classifier.topics_order)
        md_out = md_renderer.render([q1, q2])

        som_idx = md_out.find("### Strength of Materials")
        fm_idx = md_out.find("### Fluid Mechanics")
        thermo_idx = md_out.find("### Thermodynamics")

        self.assertNotEqual(som_idx, -1)
        self.assertNotEqual(fm_idx, -1)
        self.assertNotEqual(thermo_idx, -1)
        self.assertTrue(som_idx < fm_idx < thermo_idx)

    def test_11_hints_exclusion(self):
        """Test 11: Hints : block is excluded from options and question text."""
        block = RawQuestionBlock(
            qnum=1,
            page_number=1,
            header_text="Question Number : 1",
            lines=[
                RawLine("Question Number : 1", [], 1),
                RawLine("Correct Marks : 1", [], 1),
                RawLine("Sample question text.", [], 1),
                RawLine("Options :", [], 1),
                RawLine("1.", [], 1),
                RawLine("First option", [], 1),
                RawLine("2.", [], 1),
                RawLine("Second option", [], 1),
                RawLine("Hints :", [], 1),
                RawLine("This is an explanation that should be excluded", [], 1),
            ]
        )
        parser = QuestionParser()
        q_text, opts, issues = parser.parse_block(block)
        self.assertEqual(q_text, "Sample question text.")
        self.assertEqual(len(opts), 2)
        self.assertEqual(opts[0].text, "First option")
        self.assertEqual(opts[1].text, "Second option")
        for o in opts:
            self.assertNotIn("Hints", o.text)
            self.assertNotIn("explanation", o.text)

if __name__ == "__main__":
    unittest.main()
