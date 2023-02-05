from typing import Callable, List, Awaitable
from clock import TimeController
from db import Database, AnomalyDatabase
from scipy import signal
from normalization import Normalization
from datetime import date, timedelta


class ModelMachine:
    def __init__(self,
                 name: str,
                 norm: Normalization,
                 db_path: str,
                 callback: Callable[[List[float], List[float], List[float], str], Awaitable[dict]],
                 batch_size: int = 10,):
        self.vib_left = []
        self.vib_right = []
        self.temp = []
        self.batch_size = batch_size
        self.callback = callback
        self.name = name
        self.norm = norm
        self.anomaly_data_db = AnomalyDatabase(db_path)

    async def save_anomaly_data(self, message):
        await self.anomaly_data_db.save_now(name=message['name'],
                                            threshold=message['threshold'],
                                            score=message['score'])

    async def trigger(self):
        if self.is_batch():
            left, right, temp = await self.norm.norm(self.vib_left[:self.batch_size],
                                                     self.vib_right[:self.batch_size],
                                                     self.temp[:self.batch_size])
            message = await self.callback(left, right, temp, self.name)

            if message['anomaly']:
                await self.save_anomaly_data(message)

            self.clear_batch()

    def is_batch(self):
        return len(self.vib_left) >= self.batch_size \
            and len(self.temp) >= self.batch_size \
            and len(self.vib_right) >= self.batch_size

    def clear_batch(self):
        del self.vib_left[:self.batch_size]
        del self.vib_right[:self.batch_size]
        del self.temp[:self.batch_size]

    def add_vib_left(self, data):
        self.vib_left.extend(data)

    def add_vib_right(self, data):
        self.vib_right.extend(data)

    async def add_vib(self, left_data, right_data):
        self.add_vib_left(left_data)
        self.add_vib_right(right_data)
        await self.trigger()

    async def add_temp(self, data):
        self.temp.extend(data)
        await self.trigger()


class StatMachine:
    def __init__(self, name, db: Database):
        self.name = name
        self.left = Statistics()
        self.right = Statistics()
        self.temp = Statistics()
        self.time = TimeController()
        self.db = db

    async def save_day_avr(self):
        last_date = date.today() - timedelta(days=1)
        time, left, right, temp = await self.db.get_avr_by_one_day(last_date)
        if time:
            await self.db.save_day_avr(time, left, right, temp)

    async def save_hour_avr(self):
        avr_left = self.left.get_average()
        avr_right = self.right.get_average()
        avr_temp = self.temp.get_average()
        await self.db.save_now(avr_left, avr_right, avr_temp)

    async def trigger(self):
        if self.time.is_day_change():
            await self.save_day_avr()
            await self.save_hour_avr()
        elif self.time.is_hour_change():
            await self.save_hour_avr()

    async def add_vib(self, left_data, right_data):
        self.left.add(left_data)
        self.right.add(right_data)
        await self.trigger()

    async def add_temp(self, datas):
        self.temp.add(datas)
        await self.trigger()


class Statistics:
    def __init__(self):
        self.data_sum = 0
        self.size = 0

    def add(self, datas):
        self.data_sum += sum(list(map(abs, datas)))
        self.size += len(datas)

    def reset(self):
        self.data_sum = 0
        self.size = 0

    def get_average(self):
        average = self.data_sum / self.size
        self.reset()

        return average


class DataController:
    def __init__(self,
                 model_req: Callable[[List[float], List[float], List[float]], Awaitable[dict]],
                 norm: Normalization,
                 batch_size: int,
                 sampling_rate: int,
                 db_1_path: str,
                 db_2_path: str,
                 anomaly_data_db_path: str):
        db1 = Database(db_1_path)
        db2 = Database(db_2_path)

        self.machine1 = ModelMachine('machine1', norm, anomaly_data_db_path, model_req, batch_size)
        self.machine2 = ModelMachine('machine2', norm, anomaly_data_db_path, model_req, batch_size)
        self.machine1_stat = StatMachine('machine1', db1)
        self.machine2_stat = StatMachine('machine2', db2)
        self.sampling_rate = sampling_rate

    async def add_vib(self, message: dict):
        machine1_left = message['machine1_left']
        machine1_right = message['machine1_right']
        machine2_left = message['machine2_left']
        machine2_right = message['machine2_right']

        await self.machine1_stat.add_vib(machine1_left, machine1_right)
        await self.machine2_stat.add_vib(machine2_left, machine2_right)

        machine1_left_resampled = signal.resample(machine1_left, self.sampling_rate)
        machine1_right_resampled = signal.resample(machine1_right, self.sampling_rate)
        machine2_left_resampled = signal.resample(machine2_left, self.sampling_rate)
        machine2_right_resampled = signal.resample(machine2_right, self.sampling_rate)

        await self.machine1.add_vib(machine1_left_resampled, machine1_right_resampled)
        await self.machine2.add_vib(machine2_left_resampled, machine2_right_resampled)

    async def add_temp(self, message: dict):
        machine1 = message['machine1']
        machine2 = message['machine2']

        await self.machine1_stat.add_temp(machine1)
        await self.machine2_stat.add_temp(machine2)

        machine1_resampled = signal.resample(machine1, self.sampling_rate)
        machine2_resampled = signal.resample(machine2, self.sampling_rate)

        await self.machine1.add_temp(machine1_resampled)
        await self.machine2.add_temp(machine2_resampled)
