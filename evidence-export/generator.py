import requests
import json
from datetime import datetime

# In a real system, we'd use a template engine (like Jinja2) and PDF generator (like ReportLab).
# This prototype simply pulls from the API and formats a text-based report.

def generate_report():
    print("Generating NABH Evidence Report...")
    
    # Needs auth token in real life, skipping for simple prototype script
    # Assuming backend running locally on port 8000
    try:
        response = requests.get("http://localhost:8000/api/v1/evidence")
        if response.status_code != 200:
            print("Failed to fetch evidence from API")
            return
            
        evidence = response.json()
    except Exception as e:
        print(f"Error calling API: {e}")
        return
        
    report = f"VIGIL - NABH EVIDENCE REPORT\nGenerated: {datetime.now().isoformat()}\n"
    report += "=" * 50 + "\n\n"
    
    if not evidence:
        report += "No CAPA/Evidence records found.\n"
    
    # Group by chapter
    by_chapter = {}
    for item in evidence:
        chap = item.get("nabh_chapter", "UNKNOWN")
        if chap not in by_chapter:
            by_chapter[chap] = []
        by_chapter[chap].append(item)
        
    for chap, items in by_chapter.items():
        report += f"CHAPTER: {chap}\n"
        report += "-" * 50 + "\n"
        for idx, item in enumerate(items, 1):
            report += f"{idx}. Element: {item.get('nabh_element')}\n"
            report += f"   Ward: {item.get('ward_id')} | Patient: {item.get('patient_id')}\n"
            report += f"   Rule Violated: {item.get('rule_id')}\n"
            report += f"   CAPA Draft: {item.get('capa_draft')}\n"
            report += f"   Model/Rule Version: {item.get('model_version')}\n"
            report += "\n"
            
    print(report)
    
    with open("evidence-export/latest_report.txt", "w") as f:
        f.write(report)
        
    print("Saved to evidence-export/latest_report.txt")

if __name__ == "__main__":
    generate_report()
