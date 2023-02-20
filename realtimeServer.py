import asyncio
import socketio
import datetime

from asyncio import AbstractEventLoop
from uvicorn import Config, Server
from fastapi import FastAPI
from configparser import ConfigParser
from typing import List

from model import Model
from db import Database, AnomalyDatabase
from customNamespace import MachineHandler, CustomNamespace
from dataController import DataController
from normalization import Normalization
from logger import LoggerFactory


conf = ConfigParser()
conf.read('resource/config.ini')
normalization_path      = conf['norm']['path']
machine_namespace       = conf['namespace']['machine']
monitoring_namespace    = conf['namespace']['monitoring']
send_sampling_rate      = int(conf['server']['sampling_rate'])

model_path              = conf['model']['score_model']
init_data_path          = conf['model']['calc_init']
reg_model_path          = conf['model']['time_model']
model_sampling_rate     = int(conf['model']['rate'])
model_batch_size        = int(conf['model']['batch_size'])
threshold_machine1      = int(conf['model']['threshold_machine1'])
threshold_machine2      = int(conf['model']['threshold_machine2'])

db_1_path               = conf['database']['machine1']
db_2_path               = conf['database']['machine2']
anomaly_data_db_path    = conf['database']['anomaly_data']

log_path                = conf['socket_log']['directory']



''' 
    anomaly_data_db : Look up data that the model determines to be abnormal

    socket_logger   : Process socket connection logs. To save the log file, set 
                      the argument save_file to True and set save_path to the desired 
                      directory path.

    dc              : An object that performs all processing on data

    machine_handler : Customized AsyncNamespace of dataHandler program. It can receive 
                      'vib', 'temp' event and hand over to callable instance(callback)
'''


model = Model(model_path, init_data_path, reg_model_path)
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = FastAPI()


def server_load(_app, _config: ConfigParser, loop: AbstractEventLoop):
    config = Config(app=_app,
                    host=_config['server']['ip'],
                    port=int(_config['server']['port']),
                    loop=loop)
    return Server(config)


async def model_req(left: List[float], right: List[float], temp: List[float], name: str) -> dict:
    try:
        score, exp_time = await model.get_model_res(left, right, temp)

        if name == 'machine1':
            threshold = threshold_machine1
        else:
            threshold = threshold_machine2

        anomaly = score >= threshold
        message = {
            'name': name,
            'score': score,
            'remain_time': exp_time,
            'anomaly': bool(anomaly),
            'threshold': threshold
        }
        await sio.emit('model', message, namespace=monitoring_namespace)

        return message
    except Exception as error:
        print(error)


LoggerFactory.init_logger(name='socket_log',
                          save_file=True,
                          save_path=log_path)

socket_logger = LoggerFactory.get_logger()
dc = DataController(model_req, Normalization(normalization_path),
                    model_batch_size, model_sampling_rate,
                    db_1_path, db_2_path, anomaly_data_db_path)


async def add_data_by_event(event, message):
    if event == 'vib':
        await dc.add_vib(message)
    elif event == 'temp':
        await dc.add_temp(message)


async def event_handling(event, message):
    await add_data_by_event(event, message)
    await sio.emit(event, message, namespace=monitoring_namespace)


machine_handler = MachineHandler(logger=socket_logger,
                                 namespace=machine_namespace,
                                 callback=event_handling)

monitoring = CustomNamespace(logger=socket_logger,
                             namespace=monitoring_namespace)

sio.register_namespace(namespace_handler=machine_handler)
sio.register_namespace(namespace_handler=monitoring)


@app.get("/stat/{start}/{end}")
async def get_stat_month(start: datetime.date, end: datetime.date):
    try:
        machine_1_res = await Database(db_1_path).get_by_duration(start, end)
        machine_2_res = await Database(db_2_path).get_by_duration(start, end)

        return {'machine_1': machine_1_res,
                'machine_2': machine_2_res}
    except Exception as error:
        print(error)


@app.get("/stat/{date}")
async def get_stat_day(date: datetime.date):
    try:
        machine_1_res = await Database(db_1_path).get_by_one_day(date)
        machine_2_res = await Database(db_2_path).get_by_one_day(date)

        return {'machine_1': machine_1_res,
                'machine_2': machine_2_res}
    except Exception as error:
        print(error)


@app.get("/anomaly/{date}")
async def get_anomaly_day(date: datetime.date):
    try:
        res = await AnomalyDatabase(anomaly_data_db_path).get_by_one_day(date)

        return res
    except Exception as error:
        print(error)


if __name__ == "__main__":
    socket_app = socketio.ASGIApp(sio, app)
    main_loop = asyncio.get_event_loop()
    socket_server = server_load(socket_app, conf, main_loop)

    main_loop.run_until_complete(socket_server.serve())
