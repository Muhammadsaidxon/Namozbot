from pathlib import Path
from typing import List, Dict
from fpdf import FPDF


def build_prayer_pdf(title: str, city_name: str, rows: List[Dict[str, str]], output_path: str) -> str:
    city_name = city_name.replace("‘", "'").replace("’", "'")
    title = title.replace("‘", "'").replace("’", "'")

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 8, f"Shahar: {city_name}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    headers = ["Sana", "Bomdod", "Quyosh", "Peshin", "Asr", "Shom", "Xufton"]
    widths = [28, 24, 24, 24, 20, 20, 24]

    pdf.set_font("Helvetica", "B", 9)
    for header, width in zip(headers, widths):
        pdf.cell(width, 8, header, border=1, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", size=9)
    for row in rows:
        values = [
            row["date"],
            row["Bomdod"],
            row["Quyosh"],
            row["Peshin"],
            row["Asr"],
            row["Shom"],
            row["Xufton"],
        ]
        for value, width in zip(values, widths):
            pdf.cell(width, 8, str(value), border=1, align="C")
        pdf.ln()

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output))
    return str(output)
