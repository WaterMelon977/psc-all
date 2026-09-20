import json
from typing import List, Dict, Any
from src.models import Question

class JSONRenderer:
    def render(self, questions: List[Question]) -> str:
        data = {
            "questions": [q.to_dict() for q in questions]
        }
        return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
