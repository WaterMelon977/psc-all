import re
import shutil
from pathlib import Path
from collections import defaultdict

def main():
    root = Path(r"d:\appsc-loaded")
    pcb_dir = root / "pcb-ae"
    
    # 1. Ensure images are present in pcb-ae/images
    img_dir = pcb_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    
    envi_img_dir = pcb_dir / "pdfs" / "2022-ae-various-civil-envi" / "images"
    if envi_img_dir.exists():
        for f in envi_img_dir.glob("*"):
            dst = img_dir / f.name
            if not dst.exists():
                shutil.copy2(f, dst)

    mech_img_dir = pcb_dir / "pdfs" / "2022-ae-various-civil-mech" / "images"
    if mech_img_dir.exists():
        for f in mech_img_dir.glob("*"):
            dst = img_dir / f.name
            if not dst.exists():
                shutil.copy2(f, dst)

    # 2. Load topics and subtopics hierarchy
    hierarchy_path = pcb_dir / "topics.md"
    hierarchy = {}
    current_topic = None
    with open(hierarchy_path, "r", encoding="utf-8") as f:
        for line in f:
            l = line.strip()
            if not l or (l.startswith("# ") and not l.startswith("### ")):
                continue
            if l.startswith("### "):
                current_topic = re.sub(r"^###\s*", "", l).strip()
                hierarchy[current_topic] = []
            elif (l.startswith("- ") or l.startswith("* ")) and current_topic:
                sub = re.sub(r"^[-*]\s*", "", l).strip()
                hierarchy[current_topic].append(sub)

    # 3. Source files
    source_files = [
        pcb_dir / "pdfs" / "2022-ae-various-civil-envi" / "2022-ae-various-civil-envi.md",
        pcb_dir / "pdfs" / "2022-ae-various-civil-envi" / "2022-ae-various-civil-mech.md",
        pcb_dir / "pdfs" / "2022-ae-various-civil-envi" / "2025-common-subject.md",
        pcb_dir / "pdfs" / "2022-ae-various-civil-envi" / "2025-environment-analyst-grade2.md"
    ]

    compiled_data = defaultdict(lambda: defaultdict(list))

    for f_idx, f_path in enumerate(source_files):
        with open(f_path, "r", encoding="utf-8") as fp:
            text = fp.read()

        first_q = re.search(r"(?m)^## Question\s+\d+", text)
        if not first_q:
            continue
        body = text[first_q.start():]
        blocks = re.split(r"(?m)(?=^## Question\s+\d+)", body)
        for b in blocks:
            b_clean = b.strip()
            if not b_clean:
                continue

            while True:
                new_cleaned = re.sub(r'(?:\n+---+\s*|\n+#+ [^\n]+)+\s*$', '', b_clean).strip()
                if new_cleaned == b_clean:
                    break
                b_clean = new_cleaned

            q_match = re.match(r"^## Question\s+(\d+)", b_clean)
            if not q_match:
                continue
            orig_qnum = int(q_match.group(1))

            top_match = re.search(r"(?m)^\*\*Topic:\*\*\s*(.+)", b_clean)
            sub_match = re.search(r"(?m)^\*\*Subtopic:\*\*\s*(.+)", b_clean)
            exam_match = re.search(r"(?m)^### Exam\s*\n\s*([^\n]+)", b_clean)

            topic = top_match.group(1).strip() if top_match else "11.civil engineering"
            subtopic = sub_match.group(1).strip() if sub_match else ""
            exam = exam_match.group(1).strip() if exam_match else f_path.stem

            body_no_qheader = re.sub(r"^## Question\s+\d+\s*\n*", "", b_clean).strip()
            body_no_qheader = re.sub(
                r'!\[(.*?)\]\((?:\./|pcb-ae/|pdfs/[^/]+/)?images/([^)]+)\)',
                r'![\1](images/\2)',
                body_no_qheader
            )

            compiled_data[topic][subtopic].append({
                "f_idx": f_idx,
                "orig_qnum": orig_qnum,
                "exam": exam,
                "body": body_no_qheader,
                "file": f_path.name
            })

    # 4. Sequentially number questions 1 to N
    q_counter = 1
    final_blocks = []
    topic_sub_to_qnums = defaultdict(lambda: defaultdict(list))
    topic_to_qnums = defaultdict(list)

    for top in hierarchy:
        subs_in_h = hierarchy.get(top, [])
        all_subs = list(subs_in_h)
        for s in compiled_data[top]:
            if s and s not in all_subs:
                all_subs.append(s)

        if all_subs:
            for s in all_subs:
                q_list = compiled_data[top].get(s, [])
                q_list.sort(key=lambda x: (x["f_idx"], x["orig_qnum"]))
                for item in q_list:
                    cur_q = q_counter
                    q_counter += 1
                    topic_sub_to_qnums[top][s].append(cur_q)
                    topic_to_qnums[top].append(cur_q)
                    item_body = item["body"]
                    block_str = f"## Question {cur_q}\n\n{item_body}\n\n---\n"
                    final_blocks.append((top, s, cur_q, block_str))

            if "" in compiled_data[top]:
                q_list = compiled_data[top][""]
                q_list.sort(key=lambda x: (x["f_idx"], x["orig_qnum"]))
                for item in q_list:
                    cur_q = q_counter
                    q_counter += 1
                    topic_to_qnums[top].append(cur_q)
                    item_body = item["body"]
                    block_str = f"## Question {cur_q}\n\n{item_body}\n\n---\n"
                    final_blocks.append((top, "", cur_q, block_str))
        else:
            q_list = []
            for s, items in compiled_data[top].items():
                q_list.extend(items)
            q_list.sort(key=lambda x: (x["f_idx"], x["orig_qnum"]))
            for item in q_list:
                cur_q = q_counter
                q_counter += 1
                topic_to_qnums[top].append(cur_q)
                item_body = item["body"]
                block_str = f"## Question {cur_q}\n\n{item_body}\n\n---\n"
                final_blocks.append((top, "", cur_q, block_str))

    total_questions = q_counter - 1
    print(f"Total questions compiled: {total_questions}")

    # 5. Build Topic Index
    index_lines = ["# APPSC PCB All Exams Question Bank\n\n", "## Topic Index\n\n"]
    for top in hierarchy:
        index_lines.append(f"### {top}\n\n")
        subs_in_h = hierarchy.get(top, [])
        if subs_in_h:
            for s in subs_in_h:
                index_lines.append(f"#### {s}\n\n")
                qs = topic_sub_to_qnums[top].get(s, [])
                if qs:
                    for q in qs:
                        index_lines.append(f"- Q{q}\n")
                else:
                    index_lines.append("*(No questions)*\n")
                index_lines.append("\n")
        else:
            qs = topic_to_qnums[top]
            if qs:
                for q in qs:
                    index_lines.append(f"- Q{q}\n")
            else:
                index_lines.append("*(No questions)*\n")
            index_lines.append("\n")

    index_lines.append("---\n\n")

    # 6. Build Document Body
    body_lines = []
    current_top = None
    current_sub = None

    for top, sub, q_num, b_text in final_blocks:
        if top != current_top:
            current_top = top
            current_sub = None
            body_lines.append(f"# {top}\n\n")

        if sub and sub != current_sub:
            current_sub = sub
            body_lines.append(f"## {sub}\n\n")

        body_lines.append(b_text + "\n")

    full_doc = "".join(index_lines) + "".join(body_lines)

    out_file = pcb_dir / "pcb-all.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(full_doc)

    print(f"Compilation complete: {out_file}")
    print(f"Lines: {len(full_doc.splitlines())}")

if __name__ == "__main__":
    main()
