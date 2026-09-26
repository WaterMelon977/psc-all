import sys, json, os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
load_dotenv(Path("classify/.env"))
sys.path.insert(0, r"d:\appsc-loaded")
from classify.classify import load_topic_hierarchy, parse_markdown_questions, call_openrouter, build_classification_prompt_context

hierarchy = load_topic_hierarchy(r"d:\appsc-loaded\pcb-ae\topics.md")
with open(r"d:\appsc-loaded\pcb-ae\pdfs\2022-ae-various-civil-mech\2022-ae-various-civil-mech.md", encoding="utf-8") as f:
    content = f.read()

questions = parse_markdown_questions(content)

topics_list_str, has_subtopics, hierarchy = build_classification_prompt_context(hierarchy)

system_prompt = (
    "You are an expert exam classifier for APPSC exams.\n"
    "Classify each question strictly into ONE of the allowed topics, and select the best matching subtopic:\n"
    + topics_list_str
    + "\n\nRespond strictly as a JSON object where keys are question IDs as strings.\n"
    "Example:\n"
    '{"1": {"topic": "1. Ramayanam", "subtopic": "Characters"}}'
)

items_to_send = []
for q in questions[:10]:
    q_text = q["text"].replace("\n", " ").strip()
    items_to_send.append({"id": q["num"], "q": q_text[:200]})

user_prompt = json.dumps(items_to_send, ensure_ascii=False)
raw_resp = call_openrouter(user_prompt, system_prompt, os.getenv("OPENROUTER_API_KEY"), "qwen/qwen-2.5-72b-instruct")
print("Raw Response:\n", raw_resp)
