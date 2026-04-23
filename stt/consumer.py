

# import json
# import os
# import time
# import pika
# import requests
# import io

# from pydub import AudioSegment
# from django.conf import settings

# # ffmpeg path (Windows)
# os.environ["PATH"] += r";C:\ffmpeg\ffmpeg-8.1-essentials_build\bin"

# session = requests.Session()

# CHUNK_LENGTH_MS = 30 * 1000  # 20 seconds
# RETRY_COUNT = 3


# # ==============================
# # 🔹 Deepgram Request
# # ==============================
# def send_to_deepgram(audio_bytes: bytes):
#     url = "https://api.deepgram.com/v1/listen?model=nova-3&language=ar&smart_format=true"

#     headers = {
#         "Authorization": f"Token {settings.DEEPGRAM_API_KEY}",
#         "Content-Type": "audio/wav"
#     }

#     for attempt in range(RETRY_COUNT):
#         try:
#             response = session.post(
#                 url,
#                 headers=headers,
#                 data=audio_bytes,
#                 timeout=(30, 300)
#             )

#             if response.status_code == 200:
#                 data = response.json()
#                 return data["results"]["channels"][0]["alternatives"][0]["transcript"]

#             else:
#                 print(f"⚠️ Attempt {attempt+1} failed: {response.status_code}")

#         except Exception as e:
#             print(f"⚠️ Attempt {attempt+1} exception: {str(e)}")

#         time.sleep(2)

#     raise Exception("❌ Deepgram failed after retries")


# # ==============================
# # 🔹 Convert chunk to bytes (memory)
# # ==============================
# def audio_chunk_to_bytes(chunk: AudioSegment):
#     buffer = io.BytesIO()
#     chunk.export(buffer, format="wav")
#     return buffer.getvalue()


# # ==============================
# # 🔹 Process Short Audio
# # ==============================
# def process_short_audio(audio: AudioSegment):
#     print("⚡ Short audio detected → sending directly")

#     audio = audio.set_channels(1).set_frame_rate(16000)
#     audio_bytes = audio_chunk_to_bytes(audio)

#     return send_to_deepgram(audio_bytes)


# # ==============================
# # 🔹 Process Long Audio (Sequential Chunking)
# # ==============================
# def process_long_audio(audio: AudioSegment):
#     print("🔪 Long audio → splitting into chunks")

#     audio = audio.set_channels(1).set_frame_rate(16000)

#     chunks = [
#         audio[i:i + CHUNK_LENGTH_MS]
#         for i in range(0, len(audio), CHUNK_LENGTH_MS)
#     ]

#     transcripts = []

#     for idx, chunk in enumerate(chunks):
#         print(f"📤 Processing chunk {idx+1}/{len(chunks)}")

#         chunk_bytes = audio_chunk_to_bytes(chunk)
#         transcript = send_to_deepgram(chunk_bytes)

#         transcripts.append(transcript)

#     return " ".join(transcripts).strip()


# # ==============================
# # 🔹 Main Processing Logic
# # ==============================
# def process_audio(local_file_path: str):
#     print("⏳ Loading audio...")
#     audio = AudioSegment.from_file(local_file_path)

#     duration_seconds = len(audio) / 1000
#     print(f"🎧 Duration: {duration_seconds:.2f} seconds")

#     if duration_seconds < 120:
#         return process_short_audio(audio)
#     else:
#         return process_long_audio(audio)


# # ==============================
# # 🔹 RabbitMQ Callback
# # ==============================
# def callback(ch, method, properties, body):
#     try:
#         message = json.loads(body)

#         job_id = message["job_id"]
#         local_file_path = message["local_file_path"]

#         print("==========================================")
#         print(f"📥 Job received: {job_id}")
#         print(f"📁 File: {local_file_path}")

#         transcript = process_audio(local_file_path)

#         print("==========================================")
#         print(f"✅ DONE Job: {job_id}")
#         print(f"📝 Transcript: {transcript}")
#         print("==========================================")

#         # 🔥 هون لاحقًا: خزّن بالـ DB أو ابعت ل service تانية

#         ch.basic_ack(delivery_tag=method.delivery_tag)

#     except Exception as e:
#         print("==========================================")
#         print(f"❌ ERROR: {str(e)}")
#         print("==========================================")

#         ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


# # ==============================
# # 🔹 Start Consumer
# # ==============================
# def start_consumer():
#     while True:
#         try:
#             connection = pika.BlockingConnection(
#                 pika.ConnectionParameters(
#                     host=settings.RABBITMQ_HOST,
#                     heartbeat=600,
#                     blocked_connection_timeout=300
#                 )
#             )

#             channel = connection.channel()
#             channel.queue_declare(queue=settings.RABBITMQ_QUEUE, durable=True)

#             channel.basic_qos(prefetch_count=1)

#             channel.basic_consume(
#                 queue=settings.RABBITMQ_QUEUE,
#                 on_message_callback=callback
#             )

#             print("🎧 Waiting for STT jobs...")
#             channel.start_consuming()

#         except Exception as e:
#             print(f"⚠️ Connection lost: {e}")
#             print("🔄 Reconnecting in 5 seconds...")
#             time.sleep(5)


# if __name__ == "__main__":
#     start_consumer()












# import json
# import os
# import time
# import tempfile

# import numpy as np
# import noisereduce as nr
# import pika
# from django.conf import settings
# from faster_whisper import WhisperModel
# from pydub import AudioSegment


# # مهم على ويندوز إذا كنت تتعامل مع mp3 / m4a
# os.environ["PATH"] += r";C:\ffmpeg\ffmpeg-8.1-essentials_build\bin"

# # اختياري لتخفيف تحذيرات huggingface cache
# os.environ["HF_HUB_DISABLE_XET"] = "1"
# os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"


# # ==============================
# # إعدادات
# # ==============================
# LANGUAGE = "ar"
# BEAM_SIZE = 5

# # إذا عندك GPU:
# # DEVICE = "cuda"
# # COMPUTE_TYPE = "float16"
# DEVICE = "cpu"
# COMPUTE_TYPE = "int8"

# # إعدادات preprocessing
# TARGET_SAMPLE_RATE = 16000
# HIGH_PASS_HZ = 100
# LOW_PASS_HZ = 7800
# NOISE_REDUCTION_STRENGTH = 0.75  # إذا لاحظت تشويه بالكلام، خففها إلى 0.5


# # ==============================
# # تحميل الموديل مرة واحدة فقط
# # ==============================
# print("⏳ Loading faster-whisper model...")
# model = WhisperModel(
#     "medium",
#     device=DEVICE,
#     compute_type=COMPUTE_TYPE,
#     download_root="models",
# )
# print("✅ faster-whisper model loaded")


# # ==============================
# # Preprocessing
# # ==============================
# def preprocess_audio(local_file_path: str) -> str:
#     """
#     ينظف التسجيل قبل إدخاله للموديل:
#     - mono
#     - 16kHz
#     - normalize
#     - high-pass / low-pass filters
#     - noise reduction
#     ويرجع path لملف WAV نظيف مؤقت
#     """
#     print("⏳ Preprocessing audio...")

#     audio = AudioSegment.from_file(local_file_path)

#     # توحيد الصوت
#     audio = audio.set_channels(1).set_frame_rate(TARGET_SAMPLE_RATE)

#     # normalize
#     audio = audio.normalize()

#     # فلاتر خفيفة مفيدة لتسجيلات القاعات
#     audio = audio.high_pass_filter(HIGH_PASS_HZ)
#     audio = audio.low_pass_filter(LOW_PASS_HZ)

#     # تحويل إلى numpy
#     samples = np.array(audio.get_array_of_samples()).astype(np.float32)

#     # تطبيع الإشارة إلى [-1, 1]
#     max_val = float(1 << (8 * audio.sample_width - 1))
#     if max_val > 0:
#         samples = samples / max_val

#     # إزالة الضجيج
#     reduced_noise = nr.reduce_noise(
#         y=samples,
#         sr=TARGET_SAMPLE_RATE,
#         stationary=False,                 # أنسب لضجيج القاعات المتغير
#         prop_decrease=NOISE_REDUCTION_STRENGTH,
#     )

#     # رجوع إلى int16
#     reduced_noise = np.clip(reduced_noise, -1.0, 1.0)
#     reduced_int16 = (reduced_noise * 32767).astype(np.int16)

#     clean_audio = AudioSegment(
#         reduced_int16.tobytes(),
#         frame_rate=TARGET_SAMPLE_RATE,
#         sample_width=2,
#         channels=1,
#     )

#     with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
#         clean_path = tmp_file.name

#     clean_audio.export(clean_path, format="wav")
#     print(f"✅ Preprocessing done: {clean_path}")

#     return clean_path


# # ==============================
# # Transcription
# # ==============================
# def transcribe_audio(local_file_path: str) -> str:
#     clean_path = preprocess_audio(local_file_path)

#     try:
#         print("⏳ Starting transcription...")

#         segments, info = model.transcribe(
#             clean_path,
#             language=LANGUAGE,
#             beam_size=BEAM_SIZE,
#             vad_filter=True,
#             vad_parameters=dict(
#                 min_silence_duration_ms=400
#             ),
#             word_timestamps=False,
#         )

#         texts = []
#         for segment in segments:
#             text = (segment.text or "").strip()
#             if text:
#                 texts.append(text)

#         final_transcript = " ".join(texts).strip()
#         return final_transcript

#     finally:
#         if os.path.exists(clean_path):
#             os.remove(clean_path)
#             print(f"🧹 Deleted temp clean file: {clean_path}")


# # ==============================
# # RabbitMQ callback
# # ==============================
# def callback(ch, method, properties, body):
#     try:
#         message = json.loads(body)

#         job_id = message["job_id"]
#         local_file_path = message["local_file_path"]
#         original_file_name = message.get("original_file_name", "unknown")

#         print("==========================================")
#         print("📥 Received job from RabbitMQ")
#         print(f"🆔 Job ID: {job_id}")
#         print(f"📁 Original file name: {original_file_name}")
#         print(f"💾 Local file path: {local_file_path}")
#         print("==========================================")

#         if not os.path.exists(local_file_path):
#             raise FileNotFoundError(f"Audio file not found: {local_file_path}")

#         transcript = transcribe_audio(local_file_path)

#         print("==========================================")
#         print(f"✅ DONE Job: {job_id}")
#         print(f"📝 Final Transcript:\n{transcript}")
#         print("==========================================")

#         # لاحقًا:
#         # - خزّن transcript بالـ DB
#         # - أو ابعته لخدمة ثانية
#         # - أو حدّث status

#         ch.basic_ack(delivery_tag=method.delivery_tag)

#     except Exception as e:
#         print("==========================================")
#         print(f"❌ ERROR: {str(e)}")
#         print("==========================================")
#         ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


# # ==============================
# # Start consumer
# # ==============================
# def start_consumer():
#     while True:
#         try:
#             rabbitmq_host = settings.RABBITMQ_HOST
#             rabbitmq_queue = settings.RABBITMQ_QUEUE

#             connection = pika.BlockingConnection(
#                 pika.ConnectionParameters(
#                     host=rabbitmq_host,
#                     heartbeat=600,
#                     blocked_connection_timeout=300,
#                 )
#             )

#             channel = connection.channel()
#             channel.queue_declare(queue=rabbitmq_queue, durable=True)
#             channel.basic_qos(prefetch_count=1)

#             channel.basic_consume(
#                 queue=rabbitmq_queue,
#                 on_message_callback=callback,
#                 auto_ack=False,
#             )

#             print("🎧 Waiting for STT jobs...")
#             channel.start_consuming()

#         except AttributeError as e:
#             print(f"❌ Settings error: {e}")
#             break

#         except Exception as e:
#             print(f"⚠️ RabbitMQ / runtime error: {e}")
#             print("🔄 Reconnecting in 5 seconds...")
#             time.sleep(5)










import json
import os
import time
import tempfile

import numpy as np
import noisereduce as nr
import pika
from django.conf import settings
from faster_whisper import WhisperModel
from pydub import AudioSegment
from stt.mongo_store import update_job_status, save_job_result, mark_job_failed
from stt.ai_cleanup import clean_long_transcript_with_qwen_client
from stt.notification_producer import send_notification


# ==============================
# Windows / environment setup
# ==============================
os.environ["PATH"] += r";C:\ffmpeg\ffmpeg-8.1-essentials_build\bin"
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"


# ==============================
# Settings
# ==============================
LANGUAGE = "ar"
BEAM_SIZE = 5

DEVICE = "cuda"
COMPUTE_TYPE = "int8_float16"

TARGET_SAMPLE_RATE = 16000
HIGH_PASS_HZ = 100
LOW_PASS_HZ = 7800
NOISE_REDUCTION_STRENGTH = 0.75


# ==============================
# Load Whisper model once
# ==============================
print("⏳ Loading faster-whisper model...")
model = WhisperModel(
    "medium",
    device=DEVICE,
    compute_type=COMPUTE_TYPE,
    download_root="models",
)
print("✅ faster-whisper model loaded")


# ==============================
# Audio preprocessing
# ==============================
def preprocess_audio(local_file_path: str) -> str:
    print("⏳ Preprocessing audio...")

    audio = AudioSegment.from_file(local_file_path)

    audio = audio.set_channels(1).set_frame_rate(TARGET_SAMPLE_RATE)
    audio = audio.normalize()
    audio = audio.high_pass_filter(HIGH_PASS_HZ)
    audio = audio.low_pass_filter(LOW_PASS_HZ)

    samples = np.array(audio.get_array_of_samples()).astype(np.float32)

    max_val = float(1 << (8 * audio.sample_width - 1))
    if max_val > 0:
        samples = samples / max_val

    reduced_noise = nr.reduce_noise(
        y=samples,
        sr=TARGET_SAMPLE_RATE,
        stationary=False,
        prop_decrease=NOISE_REDUCTION_STRENGTH,
    )

    reduced_noise = np.clip(reduced_noise, -1.0, 1.0)
    reduced_int16 = (reduced_noise * 32767).astype(np.int16)

    clean_audio = AudioSegment(
        reduced_int16.tobytes(),
        frame_rate=TARGET_SAMPLE_RATE,
        sample_width=2,
        channels=1,
    )

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        clean_path = tmp_file.name

    clean_audio.export(clean_path, format="wav")
    print(f"✅ Preprocessing done: {clean_path}")

    return clean_path


# ==============================
# Speech-to-text
# ==============================
def transcribe_audio(local_file_path: str) -> str:
    clean_path = preprocess_audio(local_file_path)

    try:
        print("⏳ Starting transcription...")

        segments, info = model.transcribe(
            clean_path,
            language=LANGUAGE,
            beam_size=BEAM_SIZE,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=400
            ),
            word_timestamps=False,
        )

        texts = []
        for segment in segments:
            text = (segment.text or "").strip()
            if text:
                texts.append(text)

        return " ".join(texts).strip()

    finally:
        if os.path.exists(clean_path):
            os.remove(clean_path)
            print(f"🧹 Deleted temp clean file: {clean_path}")


# ==============================
# Full processing pipeline
# ==============================
def process_audio_job(local_file_path: str) -> dict:
    raw_transcript = transcribe_audio(local_file_path)
    cleaned_transcript = clean_long_transcript_with_qwen_client(raw_transcript)

    return {
        "raw_transcript": raw_transcript,
        "cleaned_transcript": cleaned_transcript,
    }

# ==============================
# Helper for notifications
# ==============================
def safe_send_notification(user_id, message, notif_type):
    try:
        send_notification(user_id, message, notif_type)
    except Exception as e:
        print(f"⚠️ Notification failed: {e}")


# ==============================
# RabbitMQ callback
# ==============================
def callback(ch, method, properties, body):
    job_id = None
    user_id = None

    try:
        message = json.loads(body)

        job_id = message["job_id"]
        local_file_path = message["local_file_path"]
        original_file_name = message.get("original_file_name", "unknown")
        user_id = message.get("user_id")

        update_job_status(job_id, "processing")

        if user_id:
            safe_send_notification(
                user_id,
                "the audio was processing",
                "transcribe"
            )

        print("==========================================")
        print("📥 Received job from RabbitMQ")
        print(f"🆔 Job ID: {job_id}")
        print(f"📁 Original file name: {original_file_name}")
        print(f"💾 Local file path: {local_file_path}")
        print("==========================================")

        if not os.path.exists(local_file_path):
            raise FileNotFoundError(f"Audio file not found: {local_file_path}")

        result = process_audio_job(local_file_path)

        raw_transcript = result["raw_transcript"]
        cleaned_transcript = result["cleaned_transcript"]

        save_job_result(
            job_id=job_id,
            raw_transcript=raw_transcript,
            cleaned_transcript=cleaned_transcript,
        )

        if user_id:
            safe_send_notification(
                user_id,
                "the audio was completed",
                "transcribe"
            )

        print("==========================================")
        print(f"✅ DONE Job: {job_id}")
        print("==========================================")

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        if job_id:
            mark_job_failed(job_id, str(e))

        if user_id:
            safe_send_notification(
                user_id,
                "the audio was failed",
                "transcribe"
            )

        print("==========================================")
        print(f"❌ ERROR: {str(e)}")
        print("==========================================")

        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
# ==============================
# Start consumer
# ==============================
def start_consumer():
    while True:
        try:
            rabbitmq_host = settings.RABBITMQ_HOST
            rabbitmq_queue = settings.RABBITMQ_QUEUE

            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=rabbitmq_host,
                    heartbeat=600,
                    blocked_connection_timeout=300,
                )
            )

            channel = connection.channel()
            channel.queue_declare(queue=rabbitmq_queue, durable=True)
            channel.basic_qos(prefetch_count=1)

            channel.basic_consume(
                queue=rabbitmq_queue,
                on_message_callback=callback,
                auto_ack=False,
            )

            print("🎧 Waiting for STT jobs...")
            channel.start_consuming()

        except AttributeError as e:
            print(f"❌ Settings error: {e}")
            break

        except Exception as e:
            print(f"⚠️ RabbitMQ / runtime error: {e}")
            print("🔄 Reconnecting in 5 seconds...")
            time.sleep(5)
if __name__ == "__main__":
    start_consumer()