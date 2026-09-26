import sys, json, os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
load_dotenv(Path("classify/.env"))
sys.path.insert(0, r"d:\appsc-loaded")
from classify.classify import load_topic_hierarchy, parse_markdown_questions, call_openrouter

hierarchy = load_topic_hierarchy(r"d:\appsc-loaded\pcb-ae\topics.md")
with open(r"d:\appsc-loaded\pcb-ae\pdfs\2022-ae-various-civil-mech\2022-ae-various-civil-mech.md", encoding="utf-8") as f:
    content = f.read()

questions = parse_markdown_questions(content)
test_batch = questions[:5]
items_to_send = [{"id": q["num"], "q": q["text"][:200]} for q in test_batch]

lines = []
for t, s in hierarchy.items():
    if s:
        subs_str = ", ".join(s)
        lines.append(f"- {t} (Subtopics: {subs_str})")
    else:
        lines.append(f"- {t}")
topics_list_str = "\n".join(lines)

system_prompt = (
    "You are an expert exam classifier for APPSC exams.\n"
    "Classify each question strictly into ONE of the allowed topics, and select the best matching subtopic:\n"
    + topics_list_str
    + "\n\nRespond strictly as a JSON object where keys are question IDs as strings."
)

resp = call_openrouter(json.dumps(items_to_send), system_prompt, os.getenv("OPENROUTER_API_KEY"), "qwen/qwen-2.5-72b-instruct")
print("LLM Response:\n", resp)
