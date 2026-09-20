import json
from src.models import ConversionReport

class ReportGenerator:
    def generate(self, report: ConversionReport) -> str:
        return json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n"
