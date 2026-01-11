def remove_white_background(img):
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    datas = img.getdata()
    new_data = []
    for item in datas:
        if item[0] > 240 and item[1] > 240 and item[2] > 240:
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append(item)
    img.putdata(new_data)
    return img

def create_certificate(student_name, course_name, logo_file=None, signature_file=None):
    from reportlab.lib.colors import HexColor
    from reportlab.lib.utils import ImageReader
    from PIL import Image
    from datetime import datetime
    import random
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    bg = HexColor("#0E1117")
    neon = HexColor("#00D4FF")
    purple = HexColor("#7D3CFF")
    light = HexColor("#FAFAFA")
    muted = HexColor("#979797")
    c.setFillColor(bg)
    c.rect(0, 0, width, height, fill=True, stroke=False)
    c.setStrokeColor(neon)
    c.setLineWidth(3)
    c.rect(25, 25, width-50, height-50)
    c.setStrokeColor(purple)
    c.setLineWidth(1)
    c.rect(35, 35, width-70, height-70)
    if logo_file:
        try:
            logo_file.seek(0)
            img = Image.open(io.BytesIO(logo_file.getvalue()))
            img = remove_white_background(img)
            r = min(250/img.width, 120/img.height)
            nw, nh = int(img.width*r), int(img.height*r)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            c.drawImage(ImageReader(buf), 50, height-nh-50, width=nw, height=nh, mask="auto")
        except: pass
    c.setFillColor(neon)
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(width-50, height-60, "VYUD AI CERTIFIED")
    c.setFillColor(light)
    c.setFont("Helvetica-Bold", 48)
    c.drawCentredString(width/2, height-180, "CERTIFICATE")
    c.setFillColor(neon)
    c.setFont("Helvetica", 20)
    c.drawCentredString(width/2, height-220, "OF COMPLETION")
    c.setStrokeColor(purple)
    c.setLineWidth(2)
    c.line(width/2-150, height-245, width/2+150, height-245)
    c.setFillColor(muted)
    c.setFont("Helvetica", 14)
    c.drawCentredString(width/2, height-280, "This certifies that")
    c.setFillColor(light)
    c.setFont("Helvetica-Bold", 36)
    c.drawCentredString(width/2, height-330, student_name)
    c.setFillColor(muted)
    c.setFont("Helvetica", 14)
    c.drawCentredString(width/2, height-370, "has successfully completed")
    c.setFillColor(neon)
    c.setFont("Helvetica-BoldOblique", 24)
    c.drawCentredString(width/2, height-410, course_name)
    if signature_file:
        try:
            signature_file.seek(0)
            img = Image.open(io.BytesIO(signature_file.getvalue()))
            img = remove_white_background(img)
            r = min(150/img.width, 60/img.height)
            nw, nh = int(img.width*r), int(img.height*r)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            c.drawImage(ImageReader(buf), 100, 80, width=nw, height=nh, mask="auto")
            c.setStrokeColor(muted)
            c.line(80, 75, 250, 75)
            c.setFillColor(muted)
            c.setFont("Helvetica", 10)
            c.drawString(80, 60, "Authorized Signature")
        except: pass
    c.setFillColor(muted)
    c.setFont("Helvetica", 12)
    dt = datetime.now().strftime("%B %d, %Y")
    c.drawRightString(width-80, 80, f"Issued: {dt}")
    c.setFont("Helvetica", 10)
    cid = f"VYUD-{random.randint(10000,99999)}"
    c.drawRightString(width-80, 60, f"Certificate ID: {cid}")
    c.save()
    buffer.seek(0)
    return buffer.getvalue()

