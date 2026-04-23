

# import pika
# import json
# import base64

# def send_to_queue(file_name, file_content):
#     connection = pika.BlockingConnection(
#         pika.ConnectionParameters(host='localhost')
#     )
#     channel = connection.channel()

#     channel.queue_declare(queue='stt_queue', durable=True)

#     encoded_content = base64.b64encode(file_content).decode('utf-8')

#     message = {
#         "file_name": file_name,
#         "file_content": encoded_content
#     }

#     channel.basic_publish(
#         exchange='',
#         routing_key='stt_queue',
#         body=json.dumps(message),
#         properties=pika.BasicProperties(
#             delivery_mode=2  # persistent message
#         )
#     )

#     connection.close()












import pika
import json
from django.conf import settings


def send_job_to_queue(job_payload):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=settings.RABBITMQ_HOST)
    )
    channel = connection.channel()

    channel.queue_declare(queue=settings.RABBITMQ_QUEUE, durable=True)

    channel.basic_publish(
        exchange='',
        routing_key=settings.RABBITMQ_QUEUE,
        body=json.dumps(job_payload),
        properties=pika.BasicProperties(
            delivery_mode=2
        )
    )

    connection.close()