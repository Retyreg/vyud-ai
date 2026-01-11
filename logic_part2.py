def transcribe_for_bot(file_path):
    """Транскрибация для Telegram бота - принимает путь к файлу"""
    try:
        import os
        from openai import OpenAI
        
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        # Конвертация в mp3 (если это видео)
        audio_path = file_path + "_converted.mp3"
        
        if file_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
            video = mp.VideoFileClip(file_path)
            if video.duration > 1200:
                video = video.subclip(0, 1200)
            video.audio.write_audiofile(audio_path, bitrate="32k", logger=None)
            video.close()
        else:
            # Аудио - тоже конвертируем для сжатия
            audio_clip = mp.AudioFileClip(file_path)
            audio_clip.write_audiofile(audio_path, bitrate="32k", logger=None)
            audio_clip.close()
        
        # Проверка размера
        size_mb = os.path.getsize(audio_path) / (1024*1024)
        if size_mb > 24:
            return "Error: File too large"
        
        # Whisper
        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1", file=audio_file, response_format="text"
            )
        
        # Чистка
        try: 
            os.remove(file_path)
            os.remove(audio_path)
        except: pass
        
        return transcript
        
    except Exception as e:
        return f"Error: {str(e)}"
