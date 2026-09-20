# EXQ: APPSC Question Bank Extraction & Structuring Engine

**EXQ** is a deterministic, rule-based pipeline for extracting, deduplicating, classifying, formatting, and structuring exam questions from APPSC (Andhra Pradesh Public Service Commission) answer-key/exam PDFs into clean Markdown and structured JSON.

---

## Key Capabilities

1. **Deterministic Processing (Zero Hallucination / No LLM Required)**:
   - Built entirely on PyMuPDF (fitz), regex parsing, and deterministic topic heuristics.
   - Fast, reproducible, and offline-capable.

2. **Bilingual Deduplication**:
   - Detects Telugu Unicode character ranges (`[\u0C00-\u0C7F]`).
   - Automatically detects and discards duplicate Telugu question blocks in bilingual papers while preserving English-only questions and standalone sections.

3. **Answer Key Extraction & Verification**:
   - Parses color spans (`srgb` green range) and visual cues to pinpoint verified correct answers.
   - Identifies single-choice, multiple-choice, or missing/ambiguous answer states, flagging uncertain questions into a dedicated review report.

4. **Hierarchical Topic Classification**:
   - Classifies each question using configurable weighted keyword and regular expression rules defined in `topics.yaml`.
   - Supports domain-specific topic order preservation in generated documentation and indices.

5. **Advanced Markdown Formatting**:
   - **Column Matching Questions**: Automatically parses `Column I ... Column II` patterns and generates clean Markdown comparison tables.
   - **Assertion & Reason Questions**: Identifies `Assertion (A)` and `Reason (R)` statements and formats them onto bolded, distinct lines.
   - **Inline Numbered Statements**: Identifies inline multi-statement questions (e.g., `1. ... 2. ... 3. ...`) and converts them into structured lists.

---

## Installation & Requirements

- Python 3.9+
- Dependencies:
  ```bash
  pip install -r requirements.txt
  ```
  *(Requirements: `PyMuPDF`, `pyyaml`)*

---

## Command Line Usage (CLI)

The CLI tool is located at `app.py`. By default, it generates output files inside a folder matching the PDF name in the same directory as the PDF.

### Basic Run
```bash
python app.py "path/to/exam.pdf"
```

### Run with Custom Topics File
```bash
python app.py "path/to/exam.pdf" -t "path/to/topics.yaml"
```

### Specify Custom Output Directory
```bash
python app.py "path/to/exam.pdf" -o "path/to/output_folder"
```

---

## Python API & Code Use Cases

You can import and use EXQ modularly within your own Python pipelines or applications.

### Use Case 1: End-to-End Extraction Programmatically

```python
from pathlib import Path
from src.pdf_extractor import PDFExtractor
from src.question_parser import QuestionParser
from src.answer_detector import AnswerDetector
from src.topic_classifier import TopicClassifier
from src.markdown_renderer import MarkdownRenderer
from src.json_renderer import JSONRenderer

pdf_file = Path("pcb-ae/pdfs/2025-GSMA.pdf")
topics_config = Path("topics_gsma.yaml")

# 1. Extract raw blocks
extractor = PDFExtractor()
raw_blocks = extractor.extract_blocks(str(pdf_file))

# 2. Parse questions and filter language duplicates
parser = QuestionParser()
questions = parser.parse_questions(raw_blocks)

# 3. Detect correct answers from visual/color cues
answer_detector = AnswerDetector()
answer_detector.attach_answers(questions, raw_blocks)

# 4. Classify topics using rule configuration
classifier = TopicClassifier.from_yaml(str(topics_config))
classifier.classify_all(questions)

# 5. Render outputs
md_renderer = MarkdownRenderer(topics_order=classifier.topics_order, paper_title=pdf_file.stem)
markdown_output = md_renderer.render(questions)

json_data = JSONRenderer.render(questions, paper_title=pdf_file.stem)

print(f"Successfully processed {len(questions)} questions.")
```

---

### Use Case 2: Using the Smart Question Formatter Standalone

You can use the formatter independently on any unstructured raw question text to convert matching columns, assertion-reasons, or statements into publication-ready Markdown:

```python
from src.question_formatter import format_question_text

# Example: Matching columns question
raw_matching = (
    "Column I (Person) Column II (Neighbour to the immediate left) "
    "(i)Q (W)B (ii)P (X)E (iii)D (Y)R (iv)R (Z)F "
    "Which is the correct match of Column I with Column II?"
)

clean_markdown = format_question_text(raw_matching)
print(clean_markdown)
```

**Output:**
```markdown
| Person | Column II |
|---|---|
| (i) Q | (W) B |
| (ii) P | (X) E |
| (iii) D | (Y) R |
| (iv) R | (Z) F |

Which is the correct match of Column I with Column II?
```

---

### Use Case 3: Filtering and Querying Questions by Topic from Output JSON

```python
import json

with open("pcb-ae/pdfs/2025-GSMA/2025-GSMA.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Filter questions for a specific syllabus domain
reasoning_questions = [
    q for q in data.get("questions", [])
    if q.get("topic") == "Mental Ability and Reasoning"
]

print(f"Found {len(reasoning_questions)} reasoning questions.")
for q in reasoning_questions[:3]:
    print(f"Q{q['question_number']}: {q['question_text'][:80]}...")
```

---

## Designing a `topics.yaml` File

The topic classifier matches questions against a deterministic scoring model defined in YAML. The markdown renderer uses the exact sequential order of topics in this file to build the Table of Contents / Topic Index.

### Configuration Schema

```yaml
topics:
  - name: "Topic Display Name"
    keywords:
      "keyword or phrase": <weight_int_1_to_10>
      "single_word": <weight_int_1_to_10>
    regex:
      - pattern: "\\b[A-Z]{3,4}\\b"
        weight: <weight_int_1_to_10>
```

### Best Practices for Designing `topics.yaml`
1. **Topic Ordering**: The sequence of `- name:` entries dictates the order in the generated Markdown index. Arrange them according to the official notification syllabus.
2. **Weight Calibration**:
   - High Specificity (`8 - 10`): Distinct terms unique to the subject (e.g., `remote sensing`, `sustainable development`, `standard deviation`, `article 370`).
   - Medium Specificity (`5 - 7`): Common domain terms (e.g., `governance`, `disaster`, `census`, `amendment`).
   - Broad/Generic (`1 - 4`): Use sparingly to prevent false positive overrides across topics.
3. **Regular Expressions (`regex`)**: Use regex patterns for case-sensitive acronyms, word-boundary assertions (`\\b`), or composite patterns (e.g., legal articles, year/summit formats).

---

### Reference Implementation: APPSC General Studies & Mental Ability (10 Topics)

Below is an optimized, production-ready `topics.yaml` tailored precisely to the 10 official syllabus topics from the APPSC notification:

```yaml
topics:
  # 1. Logical Reasoning, Analytical Ability and Logical Interpretation (Q1 to Q24, Q28, Q29 in exam structure)
  - name: Logical Reasoning and Analytical Ability
    keywords:
      sitting around a circular table: 10
      circular table: 9
      facing the centre: 9
      linear arrangement: 9
      born in a different month: 10
      alphabetical order: 8
      coding-decoding: 9
      blood relation: 9
      syllogism: 9
      venn diagram: 9
      three statements are given: 10
      two conclusions: 9
      direction sense: 8
      starts from point: 9
      left turn: 7
      right turn: 7
      odd one out: 7
      letter-cluster: 9
      word pairs: 8
      both pairs follow the same pattern: 10
      analogy: 6
      puzzle: 7
      ranking and ordering: 8
      number series: 8
      letter series: 8
      symbol series: 9
      clock and calendar: 8
      cube and dice: 8
    regex:
      - pattern: "\\bpattern as that followed by the two pairs\\b"
        weight: 10
      - pattern: "\\bquestion mark \\(\\?\\) in the given series\\b"
        weight: 9
      - pattern: "\\bstatement is followed by two conclusions\\b"
        weight: 9
      - pattern: "\\bthree statements are given, followed by\\b"
        weight: 10
      - pattern: "\\bread the given information, statement and conclusion\\b"
        weight: 10

  # 2. Data Analysis: Tabulation, Visual Representation, Summary Statistics & Interpretation (Q25 to Q30)
  - name: Data Analysis and Tabulation
    keywords:
      tabulation: 9
      bar chart: 9
      bar graph: 9
      pie chart: 9
      histogram: 9
      line graph: 9
      frequency polygon: 9
      frequency distribution: 9
      ogive: 9
      arithmetic mean: 10
      weighted arithmetic mean: 10
      geometric mean: 10
      harmonic mean: 10
      median: 9
      mode: 9
      variance: 10
      standard deviation: 10
      coefficient of variation: 10
      quartile deviation: 9
      correlation: 8
      regression: 8
      scatter diagram: 9
      summary statistics: 9
      data interpretation: 9
    regex:
      - pattern: "\\barithmetic\\s+mean\\b"
        weight: 10
      - pattern: "\\bharmonic\\s+mean\\b"
        weight: 10
      - pattern: "\\bgeometric\\s+mean\\b"
        weight: 10
      - pattern: "\\bstandard\\s+deviation\\b"
        weight: 10
      - pattern: "\\bvariance\\b"
        weight: 9

  # 3. Sustainable Development and Environmental Protection (Q43, Q45, Q49, Q54, Q60, Q79, Q91-Q105, Q108-Q110)
  - name: Sustainable Development and Environment
    keywords:
      sustainable development: 10
      sustainable development goals: 10
      sdg: 10
      sdg india index: 10
      carrying capacity: 10
      absorptive capacity: 10
      brundtland commission: 10
      environmental degradation: 9
      resource depletion: 9
      functions of the environment: 9
      renewable resource: 10
      non-renewable resource: 10
      aquatic weed: 9
      water hyacinth: 10
      mk ranjitsinh: 10
      noble m paikada: 10
      stockholm: 9
      conference on the human environment: 10
      air pollution control: 9
      appcb: 10
      andhra pradesh pollution control board: 10
      water (prevention and control of pollution) act: 10
      air (prevention and control of pollution) act: 10
      environment (protection) act: 10
      public liability insurance act: 10
      great indian bustard: 10
      greenhouse gas: 9
      carbon footprint: 9
      carbon neutrality: 9
      net zero: 9
      global warming: 8
      climate change: 8
      ipcc: 9
      biodiversity: 8
      ramsar: 10
      wetland: 8
      kyoto protocol: 10
      paris agreement: 10
      montreal protocol: 10
      ozone layer: 8
      cfc: 8
      air quality index: 9
      aqi: 9
      cpcb: 8
      environmental clearance: 9
      eia: 9
      wildlife protection act: 9
      charles elton: 10
      animal ecology: 9
    regex:
      - pattern: "\\bSDG\\b"
        weight: 10
      - pattern: "\\bcarrying\\s+capacity\\b"
        weight: 10
      - pattern: "\\babsorptive\\s+capacity\\b"
        weight: 10
      - pattern: "\\bBrundtland\\b"
        weight: 10
      - pattern: "\\brenewable\\s+resource\\b"
        weight: 10
      - pattern: "\\bnon-renewable\\s+resource\\b"
        weight: 10

  # 4. Disaster Management: vulnerability profile, mitigation, Remote Sensing & GIS (Q136 to Q150)
  - name: Disaster Management and GIS
    keywords:
      disaster management: 10
      disaster recovery: 10
      disaster mitigation: 10
      disaster risk reduction: 10
      vulnerability profile: 10
      hazard map: 10
      evacuation routes: 10
      evacuation drills: 10
      flood control: 9
      flood-prone: 9
      prepare for a hurricane: 10
      hurricane: 9
      stockpiling food: 9
      preparedness measure: 9
      mitigation strategy: 9
      ndma: 10
      sdma: 10
      ndrf: 10
      cyclone: 8
      tsunami: 9
      earthquake: 8
      richter scale: 9
      seismic zone: 9
      landslide: 8
      early warning system: 9
      remote sensing: 10
      geographic information system: 10
      gis: 9
      satellite imagery: 9
      cartosat: 9
      insat: 8
      lidar: 9
      spatial resolution: 9
    regex:
      - pattern: "\\bGIS\\b"
        weight: 9
      - pattern: "\\bvulnerability\\s+profile\\b"
        weight: 10
      - pattern: "\\bhazard\\s+map\\b"
        weight: 10
      - pattern: "\\bdisaster\\b"
        weight: 8

  # 5. Geography of India with focus on Andhra Pradesh (Q77, Q83-Q90, Q118)
  - name: Geography of India and AP
    keywords:
      himalayas: 8
      western ghats: 8
      eastern ghats: 8
      araku: 8
      bay of bengal island: 9
      islands/islets: 9
      monsoon: 8
      godavari: 9
      krishna river: 9
      penna: 9
      tungabhadra: 8
      alluvial soil: 8
      black soil: 8
      regur: 8
      red soil: 7
      laterite: 8
      mangrove: 8
      coromandel: 8
      pulicat lake: 9
      kolleru lake: 9
      recorded forest area: 9
      kotha koduru beach: 10
      ramatheerdam beach: 10
      beach: 7
      universities location: 9
      acharya ng ranga agricultural: 10
      sri venkateswara veterinary: 10
      dr ysr horticultural: 10
      krishna university machilipatnam: 10
      visakhapatnam port: 8
      gangavaram port: 8
      krishnapatnam port: 8
      bauxite: 8
      mica: 8
      limestone: 7
      coal mining: 8
      sccl: 9
      singareni: 9
      agriculture integrated command and control: 9
    regex:
      - pattern: "\\bKoppen\\b"
        weight: 9
      - pattern: "\\bRecorded\\s+Forest\\s+Area\\b"
        weight: 10

  # 6. History of India (focus on social, economic, cultural, AP & National Movement) (Q61-Q76)
  - name: History of India and AP
    keywords:
      indus valley: 9
      harappa: 9
      mohenjodaro: 9
      vedic: 8
      buddhism: 8
      jainism: 8
      ashoka: 9
      maurya: 8
      gupta: 8
      mughal: 8
      akbar: 8
      vijayanagara: 9
      krishnadevaraya: 10
      satavahana: 10
      kakatiya: 10
      ellora caves: 10
      hasya sanjeevani: 10
      kandukuri veeresalingam: 10
      gurajada apparao: 10
      tanguturi prakasam: 10
      andhra mahasabha: 10
      alluri sitarama raju: 10
      potti sreeramulu: 10
      freedom struggle of india: 10
      muhammedan literary society: 10
      nawab abdul latif: 10
      rabindranath tagore: 10
      gitanjali: 10
      chittoor district rebellion: 10
      poligars: 10
      madras native association: 10
      gajula lakshminarasu chetty: 10
      social reformers in andhra: 10
      swadeshi movement: 9
      home rule: 8
      rowlatt act: 9
      jallianwala bagh: 10
      khilafat movement: 9
      non-cooperation: 9
      civil disobedience: 9
      quit india: 9
      subhas chandra bose: 8
      bhagat singh: 8
      1857 revolt: 9
      sepoy mutiny: 9
      indian national congress: 8
    regex:
      - pattern: "\\bINC\\b"
        weight: 7
      - pattern: "\\bTagore\\b"
        weight: 9
      - pattern: "\\bEllora\\b"
        weight: 9

  # 7. Indian Polity and Governance: constitutional issues, public policy, reforms & e-Governance (Q40, Q42, Q107, Q114, Q116, Q117)
  - name: Indian Polity and Governance
    keywords:
      constitution of india: 9
      constitution amendment act: 10
      106th constitution amendment: 10
      129th amendment: 10
      amendment bill: 9
      lok sabha elections: 9
      election commission: 9
      juvenile courts: 9
      digital initiatives: 8
      digilocker: 9
      umang: 9
      diksha: 9
      e-governance: 10
      digital india: 8
      preamble: 9
      fundamental rights: 9
      directive principles: 9
      dpsp: 9
      fundamental duties: 9
      basic structure: 9
      supreme court: 8
      high court: 7
      judicial review: 9
      governor: 7
      ordinance: 7
      panchayati raj: 9
      73rd amendment: 10
      74th amendment: 10
      finance commission: 9
      cag: 9
      upsc: 7
      anti-defection law: 9
      right to information: 9
      rti: 8
    regex:
      - pattern: "\\bAmendment\\s+(?:Act|Bill)?\\b"
        weight: 9
      - pattern: "Article\\s+\\d+"
        weight: 9
      - pattern: "\\bLok\\s+Sabha\\b"
        weight: 7

  # 8. Indian Economy and Planning (Q115, Q121 to Q135)
  - name: Indian Economy and Planning
    keywords:
      gross domestic product: 9
      gdp: 7
      gva: 8
      second five-year plan: 10
      five-year plan: 9
      green revolution: 9
      poverty line: 9
      insolvency and bankruptcy code: 10
      ibc: 9
      all-india financial institutions: 10
      aifis: 10
      refinance institution: 10
      nabard: 10
      ifci: 9
      tfci: 9
      national fiscal: 8
      interoperable atm network: 9
      national financial switch: 10
      nfs: 8
      small finance bank: 9
      equitas small finance bank: 10
      microfinance industry network: 10
      mfin: 9
      nbfc-mfis: 10
      top textile industries: 9
      demographic condition of india during the british period: 10
      share of different categories of employment: 9
      events in india's economy: 9
      uzhavar sandhai: 9
      farmers market: 8
      inflation: 8
      monetary policy: 9
      repo rate: 9
      reserve bank: 7
      rbi: 7
      fiscal deficit: 9
      planning commission: 8
      niti aayog: 9
      goods and services tax: 9
      gst: 8
      fdi: 8
      balance of payments: 8
    regex:
      - pattern: "\\bAIFIs?\\b"
        weight: 10
      - pattern: "\\bNABARD\\b"
        weight: 10
      - pattern: "\\bIBC\\b"
        weight: 9
      - pattern: "\\bFive-year\\s+Plan\\b"
        weight: 10
      - pattern: "\\bNFS\\b"
        weight: 8

  # 9. General Science and Technology (Q44, Q46, Q50-Q53, Q55-Q58, Q113, Q119)
  - name: General Science and Technology
    keywords:
      param rudra: 10
      supercomputer: 9
      super computer: 9
      param shivay: 10
      param pravega: 10
      ministry of electronics & information technology: 10
      meity: 9
      food preservative: 10
      sorbic acid: 10
      aromatic solvent: 9
      reinforced plastics and resins: 9
      styrene: 9
      bacterial infections: 8
      prontosil: 10
      mould: 7
      bacteria: 7
      fungus: 7
      yeast: 7
      portuguese man o' war: 10
      hydrozoan: 10
      eduard buchner: 10
      transmission carriers: 9
      charge of electrons: 10
      de magnette: 10
      compass needle: 9
      physicists: 9
      gatterman-koch: 10
      organic chemical reactions: 9
      photosynthesis: 8
      mitochondria: 8
      dna: 8
      rna: 8
      crispr: 10
      vaccine: 8
      semiconductor: 9
      artificial intelligence: 9
      quantum computing: 10
    regex:
      - pattern: "\\bPARAM\\b"
        weight: 10
      - pattern: "\\bMeitY\\b"
        weight: 10
      - pattern: "\\bsupercomputer\\b"
        weight: 9

  # 10. Major Current Events and Issues (Q31-Q39, Q41, Q48, Q59, Q81-Q82, Q106, Q111-Q112, Q120)
  - name: Current Events and Issues
    keywords:
      nobel prize: 10
      oscar award: 10
      padma vibhushan: 10
      padma shri: 10
      padma bhushan: 9
      bharat ratna: 10
      sworn as the president: 9
      ministerial event: 8
      mission innovation: 9
      pm-pranam: 10
      paat-mitro: 10
      global pulse confederation: 10
      national nutrition programmes: 9
      infant mortality rates: 8
      international religious freedom: 9
      village health clinics: 9
      polavaram project authority: 10
      summit: 8
      g20: 9
      isro: 9
      chandrayaan: 10
      aditya l1: 10
      gaganyaan: 10
      pslv: 9
      gslv: 9
      insat-3ds: 10
      xposat: 10
      schemes by the government of india was launched in the year 2023: 10
      pradhan mantri vishwakarma: 10
    regex:
      - pattern: "\\bNobel\\s+Prize\\b"
        weight: 10
      - pattern: "\\bOscar\\b"
        weight: 10
      - pattern: "\\bPadma\\s+(?:Vibhushan|Shri|Bhushan)\\b"
        weight: 10
      - pattern: "\\bISRO\\b|\\bPSLV\\b|\\bGSLV\\b"
        weight: 8
```

---

## Output Structure

When executed, EXQ produces four synchronized artifacts:
- `<name>.md`: Clean, high-readability Markdown document with an indexed table of contents.
- `<name>.json`: Machine-readable, strictly schema-validated JSON format for databases, search indexing, or LLM evaluation.
- `<name>_review.md`: Flags edge-case questions (missing answers, ambiguous color spans, or multiple correct keys).
- `<name>_report.json`: Metrics report covering question count, answer detection rate, and topic distribution.

