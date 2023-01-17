#!/usr/bin/env python
import requests
from glob import glob
import pika, sys, os, json, traceback
from villas.dataprocessing.readtools import *
from villas.dataprocessing.timeseries import *
import villas.dataprocessing.validationtools as validationtools
import dpsimpy, dpsimpyvillas
import zipfile
import logging
import base64

#
# Start executing the dpsim simulation
#
# files - the names of the files containing the model
#
def run_dpsim(dpsim_config):
    logging.info("Requested simulation config: %s", dpsim_config)

    model_files      = dpsim_config["model_files"]
    load_profiles    = dpsim_config["load_profile_files"]
    results_file_id  = dpsim_config["results_file_id"]
    name             = 'CIGRE_MV'
    reader           = dpsimpy.CIMReader(name)
    system           = reader.loadCIM(50, model_files, dpsimpy.Domain.SP,
                                      dpsimpy.PhaseType.Single, dpsimpy.GeneratorType.PVNode)
    system
    logging.info("Starting dpsim with model files: %s", str(model_files))
    logging.info("Starting dpsim with load profile files: %s", str(load_profiles))

    sim = dpsimpy.RealTimeSimulation(name)
    sim.set_system(system)

    # map from CSV to simulation names
    assignList = {
        'LOAD-H-1': 'Load_H_1',
        'LOAD-H-3': 'Load_H_3',
        'LOAD-H-4': 'Load_H_4',
        'LOAD-H-5': 'Load_H_5',
        'LOAD-H-6': 'Load_H_6',
        'LOAD-H-8': 'Load_H_8',
        'LOAD-H-10': 'Load_H_10',
        'LOAD-H-11': 'Load_H_11',
        'LOAD-H-12': 'Load_H_12',
        'LOAD-H-14': 'Load_H_14',
        'LOAD-I-1': 'Load_I_1',
        'LOAD-I-3': 'Load_I_3',
        'LOAD-I-7': 'Load_I_7',
        'LOAD-I-9': 'Load_I_9',
        'LOAD-I-10': 'Load_I_10',
        'LOAD-I-12': 'Load_I_12',
        'LOAD-I-13': 'Load_I_13',
        'LOAD-I-14': 'Load_I_14'
    }

    if dpsim_config["load_profile_files"] != "":
        csvreader = dpsimpy.CSVReader(name, "/etc/config/loadprofile/",
                                      assignList, dpsimpy.LogLevel.info)
        csvreader.assignLoadProfile(system, 0, dpsim_config['timestep'], dpsim_config['finaltime'],
                                    dpsimpy.CSVReaderMode.MANUAL, dpsimpy.CSVReaderFormat.SECONDS)

    # instantiate logger
    logger = dpsimpy.Logger(name)

    # setup simulation
    if hasattr(dpsimpy.Domain, dpsim_config['domain']):
        domain = getattr(dpsimpy.Domain, dpsim_config['domain'])
        sim.set_domain(domain)
    if hasattr(dpsimpy.Solver, dpsim_config['solver']):
        solver = getattr(dpsimpy.Solver, dpsim_config['solver'])
        sim.set_solver(solver)
    sim.set_time_step(dpsim_config['timestep'])
    sim.set_final_time(dpsim_config['finaltime'])
    sim.add_logger(logger)

    if "villas_interface" in dpsim_config:
        # setup VILLASnode
        intf_mqtt = dpsimpyvillas.InterfaceVillas(name='MQTT', config='''{
            "type": "mqtt",
            "host": "mosquitto",
            "in": {
                "subscribe": "mqtt-dpsim"
            },
            "out": {
                "publish": "dpsim-mqtt"
            }
        }''')
        sim.add_interface(intf_mqtt, False)

        # setup exports
        for i in range(15):
            objname = 'N'+str(i)
            sim.export_attribute(sim \
                .get_idobj_attr(objname, 'v') \
                .derive_coeff(0,0) \
                .derive_mag(), 2*i)
            sim.export_attribute(sim \
                .get_idobj_attr(objname, 'v') \
                .derive_coeff(0,0) \
                .derive_phase(), 2*i+1)

    # log exports
    for node in system.nodes:
        sim.log_idobj_attribute(node.name(), 'v')

    try:
        error = ""

        logging.info("Simulation starting")

        sim.run(1)

        logging.info("Simulation complete, uploading results")

        path = 'logs/'
        logName = 'CIGRE_MV'
        dpsim_result_file = path + logName + '.csv'
        with open(dpsim_result_file, 'rb') as f:
            result_bytes = f.read().decode('utf-8').encode('ascii')
            base64_bytes = base64.b64encode(result_bytes)
            base64_ascii = base64_bytes.decode('ascii')
            r = requests.put("http://sogno-file-service:8080/api/files/"+results_file_id,
                             files={'file': '{"ready":"true", "content":"' + base64_ascii + '"}'})
        string_content = r.content.decode('utf8')        # possible source of UnicodeDecodeError
        json_content = json.loads(string_content)        # possible source of JSONDecodeError
        file_id      = json_content["data"]["fileID"]
        # Generate exceptions:
        # other_value  = "\xc3\x28".decode('utf8')       # generate UnicodeDecodeError
        # other_value  = json.loads('{"hhh":"jdk}')      # generate json.JSONDecodeError
        # other_value  = json_content["ohno"]            # generate Exception
        logging.info('Uploaded results to fileID: %s', file_id)

    except UnicodeDecodeError:
        logging.error("Failed to decode data as utf8 bytes %s", r.content)
        error = "Failed to decode data as utf8 bytes.\n" + traceback.format_exc()
    except json.JSONDecodeError:
        logging.error("Failed to decode data as json %s", string_content)
        error = "Failed to decode data as json.\n" + traceback.format_exc()
    except Exception as e:
        logging.error("Caught exception e:\n%s" + traceback.format_exc())
        error = "Caught exception e:\n" + traceback.format_exc()

    if error != "":
        r = requests.put("http://sogno-file-service:8080/api/files/"+results_file_id,
                         files={'file': '{"ready":"false", "error": ' + error + '"}'})
    return

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
    logging.info('Downloading file: %s', url)

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

def download_zipped_data(model, directory):
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
    ch.close()
    received = body.decode("utf-8")
    data = None

    try:
        data = json.loads(received)
    except Exception as e:
        logging.info("Error parsing message, invalid json: " + str(e))

    dpsim_config = {}

    try:
        if data != None and 'load_profile' in data and data['load_profile'] != "":
            download_zipped_data(data['load_profile'], '/etc/config/loadprofile')
            dpsim_config["load_profile_files"] = unzip_files('/etc/config/loadprofile/')
        else:
            logging.info("No load_profile in %s", dpsim_config)
            dpsim_config["load_profile_files"] = ""
        if data != None and 'model' in data:
            download_zipped_data(data['model'], '/etc/config/model')
            logging.info("PARAMETERS: %s", data["parameters"])
            dpsim_config["model_files"] = unzip_files('/etc/config/model/')
            dpsim_config["results_file_id"] = data["parameters"]["results_file"]
            dpsim_config["domain"] = data["parameters"]["domain"]
            dpsim_config["solver"] = data["parameters"]["solver"]
            dpsim_config["timestep"] = data["parameters"]["timestep"]
            dpsim_config["finaltime"] = data["parameters"]["finaltime"]
            logging.info("The status will be upated in file with id: %s", dpsim_config["results_file_id"])
        else:
            logging.info("No model in", dpsim_config)
    except KeyError as e:
        logging.error("Error trying to read from message:" + str(e))

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

    channel.queue_declare(queue='dpsim-worker-queue')

    channel.basic_consume(queue='dpsim-worker-queue', on_message_callback=callback, auto_ack=True)

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
