from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def generate_pdf_report(file_path, results, average_score):
    c = canvas.Canvas(file_path, pagesize=A4)

    width, height = A4
    y = height - 50

    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, y, "Smart Interview Preparation Report")

    y -= 40

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, f"Overall Score: {average_score}%")

    y -= 40

    c.setFont("Helvetica", 11)

    for index, result in enumerate(results, start=1):
        c.drawString(50, y, f"Question {index}: {result['question']}")
        y -= 20

        c.drawString(50, y, f"Answer: {result['answer'][:90]}")
        y -= 20

        c.drawString(50, y, f"Score: {result['score']}%")
        y -= 20

        c.drawString(50, y, f"Feedback: {result['feedback']}")
        y -= 30

        if y < 100:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 11)

    c.save()