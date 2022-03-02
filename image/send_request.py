#!/usr/bin/env python
import pika, sys

if len(sys.argv) > 1:
    config_filename = sys.argv[1]
else:
    config_filename = '/var/example.json'

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='rabbitmq'))
channel = connection.channel()

channel.queue_declare(queue='hello')

import json

with open(config_filename) as json_file:
    body = json_file.read()
    print(body)

channel.basic_publish(exchange='', routing_key='hello', body=json.dumps(body))
print(" [x] Sent '%s'" % body)
connection.close()
