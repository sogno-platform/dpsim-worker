#!/usr/bin/env python
import requests
from glob import glob
import pika, sys, os, json
from villas.dataprocessing.readtools import *
from villas.dataprocessing.timeseries import *
import villas.dataprocessing.validationtools as validationtools
import dpsimpy
import zipfile
import logging
import base64

def download_grid_data(name, url):
    with open(name, 'wb') as out_file:
        content = requests.get(url, stream=True).content
        out_file.write(content)

#
# Start executing the dpsim simulation
#
# files - the names of the files containing the model
#
def run_dpsim(dpsim_config):
    files            = dpsim_config["files"]
    logging.info("Starting dpsim with model files: %s", str(files))
    results_file_id  = dpsim_config["results_file_id"]
    name             = 'CIGRE_MV'
    reader           = dpsimpy.CIMReader(name)
    system           = reader.loadCIM(50, files, dpsimpy.Domain.SP, dpsimpy.PhaseType.Single, dpsimpy.GeneratorType.PVNode)
    system

    sim = dpsimpy.Simulation(name)
    sim.set_system(system)
    sim.set_domain(dpsimpy.Domain.SP)
    sim.set_solver(dpsimpy.Solver.NRP)

    logger = dpsimpy.Logger(name)
    for node in system.nodes:
        logger.log_attribute(node.name()+'.V', 'v', node)
    sim.add_logger(logger)
    sim.run()

    path = 'logs/'
    logName = 'CIGRE_MV'
    dpsim_result_file = path + logName + '.csv'
    with open(dpsim_result_file, 'rb') as f:
        result_bytes = f.read().decode('utf-8').encode('ascii')
        base64_bytes = base64.b64encode(result_bytes)
        base64_ascii = base64_bytes.decode('ascii')
        r = requests.put("http://sogno-file-service:8080/api/files/"+results_file_id, files={'file': '{"ready":"true", "content":"' + base64_ascii + '"}'})
    try:
        string_content = r.content.decode('utf8')
    except UnicodeDecodeError:
        logging.error("Failed to decode data as utf8 bytes %s", r.content)
        return
    try:
        json_content = json.loads(string_content)
        file_id      = json_content["data"]["fileID"]
    except JSONDecodeError:
        logging.error("Failed to decode data as json %s", string_content)
        return
    logging.info('Uploaded results to fileID: %s', file_id)

def get_url_list(model):
    type = model.get('type', 'url')
    if type not in ['url', 'url-list']:
        raise RuntimeError('Invalid model type')

    urls = []
    urls = model.get('url')
    if not urls:
        raise RuntimeError('Missing model url')

    if type == 'url':
        urls = [ urls ]

    return urls

def download_file(url, headers, directory):
    logging.info('Downloading model: %s', url)

    r = requests.get(url,
        headers=headers)
    r.raise_for_status()

    try:
        d = r.headers['content-disposition']
        logging.info('Content Disposition: %s', d)
        filename = re.findall("filename=(.+?(?=\;|$))", d)[0].strip('"')
    except KeyError:
        parts = url.split("/")
        filename = parts[len(parts)-1]

    with open(os.path.join(directory, filename), 'wb') as f:
        f.write(r.content)

def unzip_files(directory):
    arr = os.listdir(directory)
    for filename in arr:
        if filename.endswith('.zip'):
            with zipfile.ZipFile(directory + filename,"r") as zip_ref:
                zip_ref.extractall(directory)
            os.remove(directory + filename)

    arr = glob(directory + '*')
    logging.info("Unzipped files: " + str(arr))
    return arr

def download_model(model, directory):
    url_list = get_url_list(model)

    token = model.get('token')
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'

    for url in url_list:
        download_file(url, headers, directory)

    # print contents of directory with downloaded models
    arr = os.listdir(directory)
    logging.info("Downloaded models: " + str(arr))

def callback(ch, method, properties, body):
    logging.info("Received a message: " + str(body))
    received = body.decode("utf-8")
    data = None

    try:
        data = json.loads(received)
    except Exception as e:
        logging.info("Error parsing message, invalid json: " + str(e))

    dpsim_config = {}

    if data != None and data['model'] != None:
        download_model(data['model'], '/etc/config/model')
        dpsim_config["files"] = unzip_files('/etc/config/model/')
        dpsim_config["results_file_id"] = data["parameters"]["results_file"]
        logging.info("The status will be upated in file with id: %s", dpsim_config["results_file_id"])

    run_dpsim(dpsim_config)

def configure_logging():
    print("Configuring logging")
    # Match DPsim spdlog loglevels
    logging.addLevelName(logging.CRITICAL, 'critial')
    logging.addLevelName(logging.ERROR, 'error')
    logging.addLevelName(logging.WARNING, 'warn')
    logging.addLevelName(logging.INFO, 'info')
    logging.addLevelName(logging.DEBUG, 'debug')

    logging.basicConfig(level=logging.DEBUG,
        format='[%(asctime)s.%(msecs)d %(name)s %(levelname)s] %(message)s',
        datefmt='%H:%M:%S')

    # by default these libraries send lots of debug messages to the logging system
    logging.getLogger("pika").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

def open_rabbitmq_connection():
    logging.info("Opening rabbitmq connection")
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
    channel = connection.channel()

    channel.queue_declare(queue='hello')

    channel.basic_consume(queue='hello', on_message_callback=callback, auto_ack=True)

    logging.info(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()

def main():
    configure_logging()
    open_rabbitmq_connection()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logging.info('Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
else:
    print("NAME: ", __name__)
