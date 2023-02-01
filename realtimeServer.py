import asyncio
import socketio
import datetime

from asyncio import AbstractEventLoop
from uvicorn import Config, Server
from fastapi import FastAPI
from configparser import ConfigParser
from typing import List


from model import Model
from db import Database
from machineHandler import MachineHandler
from dataController import DataController
from normalization import Normalization


conf = ConfigParser()
conf.read('resource/config.ini')
model_path = conf['model']['score_model']
init_data_path = conf['model']['calc_init']
reg_model_path = conf['model']['time_model']
db_1_path = conf['database']['machine1']
db_2_path = conf['database']['machine2']
model_sampling_rate = int(conf['model']['rate'])
model_batch_size = int(conf['model']['batch_size'])
threshold_machine1 = int(conf['model']['threshold_machine1'])
threshold_machine2 = int(conf['model']['threshold_machine2'])
send_sampling_rate = int(conf['server']['sampling_rate'])
normalization_path = conf['norm']['path']
machine_namespace = conf['namespace']['machine']
monitoring_namespace = conf['namespace']['monitoring']

model = Model(model_path, init_data_path, reg_model_path)
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = FastAPI()


def server_load(_app, _config: ConfigParser, loop: AbstractEventLoop):
    config = Config(app=_app,
                    host=_config['server']['ip'],
                    port=int(_config['server']['port']),
                    loop=loop)
    return Server(config)


async def model_req(left: List[float], right: List[float], temp: List[float], name: str):
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
    except Exception as error:
        print(error)


dc = DataController(model_req, Normalization(normalization_path),
                    model_batch_size, model_sampling_rate, db_1_path, db_2_path)


async def add_data_by_event(event, message):
    if event == 'vib':
        await dc.add_vib(message)
    elif event == 'temp':
        await dc.add_temp(message)


async def distribute(event, message):
    resampled_message = message

    await add_data_by_event(event, message)
    await sio.emit(event, resampled_message, namespace=monitoring_namespace)

machine_handler = MachineHandler(namespace=machine_namespace, callback=distribute)
sio.register_namespace(namespace_handler=machine_handler)


@app.get("/{start}/{end}")
async def get_stat_month(start: datetime.date, end: datetime.date):
    try:
        machine_1_res = await Database(db_1_path).get_by_duration(start, end)
        machine_2_res = await Database(db_2_path).get_by_duration(start, end)

        return {'machine_1': machine_1_res, 'machine_2': machine_2_res}
    except Exception as e:
        print(e)


@app.get("/{date}")
async def get_stat_day(date: datetime.date):
    try:
        machine_1_res = await Database(db_1_path).get_by_one_day(date)
        machine_2_res = await Database(db_2_path).get_by_one_day(date)

        return {'machine_1': machine_1_res,
                'machine_2': machine_2_res}
    except Exception as error:
        print(error)


if __name__ == "__main__":
    socket_app = socketio.ASGIApp(sio, app)
    main_loop = asyncio.get_event_loop()
    socket_server = server_load(socket_app, conf, main_loop)

    main_loop.run_until_complete(socket_server.serve())
