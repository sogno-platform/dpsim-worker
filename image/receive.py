#!/usr/bin/env python
import pika, sys, os, json

def callback(ch, method, properties, body):
    data = json.loads(body.decode("utf-8"))
    print("Received a message", data)
    try:
        parsed_json = json.loads(data)
    except Exception as e:
        print("Error parsing message, invalid json: ", e)
        parsed_json = None

    if parsed_json != None:
        env = os.environ.copy()
        env["VILLAS_PAYLOAD_FILE"] = "/etc/config/config.json"
        os.environ.update(env)
        with open(env["VILLAS_PAYLOAD_FILE"], "w") as text_file:
            text_file.write(data)
        os.execv("python", [ "python", "/run.py" ])

def main():
    print("Opening rabbitmq connection")
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
    channel = connection.channel()

    channel.queue_declare(queue='hello')

    channel.basic_consume(queue='hello', on_message_callback=callback, auto_ack=True)

    print(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
else:
    print("NAME: ", __name__)
