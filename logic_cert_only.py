import io
import random
from datetime import datetime
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import HexColor

def remove_white_background(img):
    """
    Убирает белый/светлый фон из изображения.
    """
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    datas = img.getdata()
    new_data = []
    
    # Порог чувствительности (можно подкрутить)
    threshold = 240
    
    for item in datas:
        # Если пиксель светлый (R, G и B > threshold)
        if item[0] > threshold and item[1] > threshold and item[2] > threshold:
            new_data.append((255, 255, 255, 0)) # Прозрачный
        else:
            new_data.append(item)
    
    img.putdata(new_data)
    return img
    return img

def create_certificate(student_name, course_name, logo_file=None, signature_file=None):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    
    # === СТИЛЬ VYUD: Deep Space Neon ===
    bg_void = HexColor("#0E1117")
    accent_neon = HexColor("#00D4FF")
    accent_purple = HexColor("#7D3CFF")
    text_light = HexColor("#FAFAFA")
    text_muted = HexColor("#979797")
    
    # 1. Фон
    c.setFillColor(bg_void)
    c.rect(0, 0, width, height, fill=True, stroke=False)
    
    # 2. Рамки
    c.setStrokeColor(accent_neon)
    c.setLineWidth(3)
    c.rect(25, 25, width-50, height-50)
    
    c.setStrokeColor(accent_purple)
    c.setLineWidth(1)
    c.rect(35, 35, width-70, height-70)
    
    # 3. Логотип (с авто-удалением фона)
    if logo_file is not None:
        try:
            # Сброс курсора и чтение
            logo_file.seek(0)
            logo_data = logo_file.getvalue()
            logo_img = Image.open(io.BytesIO(logo_data))
            
            # Магия прозрачности
            logo_img = remove_white_background(logo_img)
            
            # Расчет размеров
            max_w, max_h = 250, 120
            ratio = min(max_w / logo_img.width, max_h / logo_img.height)
            new_w = int(logo_img.width * ratio)
            new_h = int(logo_img.height * ratio)
            
            logo_buffer = io.BytesIO()
            logo_img.save(logo_buffer, format='PNG')
            logo_buffer.seek(0)
            
            # Рисуем
            c.drawImage(ImageReader(logo_buffer), 50, height - new_h - 50, width=new_w, height=new_h, mask='auto')
        except Exception as e:
            print(f"Logo error: {e}")
    
    # 4. Текстовая часть
    c.setFillColor(accent_neon)
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(width - 50, height - 60, "VYUD AI CERTIFIED")
    
    c.setFillColor(text_light)
    c.setFont("Helvetica-Bold", 48)
    c.drawCentredString(width/2, height - 180, "CERTIFICATE")
    
    c.setFillColor(accent_neon)
    c.setFont("Helvetica", 20)
    c.drawCentredString(width/2, height - 220, "OF COMPLETION")
    
    c.setStrokeColor(accent_purple)
    c.setLineWidth(2)
    c.line(width/2 - 150, height - 245, width/2 + 150, height - 245)
    
    c.setFillColor(text_muted)
    c.setFont("Helvetica", 14)
    c.drawCentredString(width/2, height - 280, "This certifies that")
    
    c.setFillColor(text_light)
    c.setFont("Helvetica-Bold", 36)
    c.drawCentredString(width/2, height - 330, student_name)
    
    c.setFillColor(text_muted)
    c.setFont("Helvetica", 14)
    c.drawCentredString(width/2, height - 370, "has successfully completed the course")
    
    c.setFillColor(accent_neon)
    c.setFont("Helvetica-BoldOblique", 24)
    c.drawCentredString(width/2, height - 410, course_name)
    
    # 5. Подпись (с авто-удалением фона)
    if signature_file is not None:
        try:
            signature_file.seek(0)
            sig_data = signature_file.getvalue()
            sig_img = Image.open(io.BytesIO(sig_data))
            
            # Магия прозрачности
            sig_img = remove_white_background(sig_img)
            
            max_w, max_h = 150, 60
            ratio = min(max_w / sig_img.width, max_h / sig_img.height)
            new_w = int(sig_img.width * ratio)
            new_h = int(sig_img.height * ratio)
            
            sig_buffer = io.BytesIO()
            sig_img.save(sig_buffer, format='PNG')
            sig_buffer.seek(0)
            
            c.drawImage(ImageReader(sig_buffer), 100, 80, width=new_w, height=new_h, mask='auto')
            
            c.setStrokeColor(text_muted)
            c.setLineWidth(1)
            c.line(80, 75, 250, 75)
            c.setFillColor(text_muted)
            c.setFont("Helvetica", 10)
            c.drawString(80, 60, "Authorized Signature")
        except Exception as e:
            print(f"Signature error: {e}")
    
    # 6. Футер
    c.setFillColor(text_muted)
    c.setFont("Helvetica", 12)
    c.drawRightString(width - 80, 80, f"Issued: {datetime.now().strftime('%B %d, %Y')}")
    
    cert_id = f"VYUD-{random.randint(10000, 99999)}"
    c.setFont("Helvetica", 10)
    c.drawRightString(width - 80, 60, f"Certificate ID: {cert_id}")
    
    c.save()
    buffer.seek(0)
    return buffer.getvalue()
