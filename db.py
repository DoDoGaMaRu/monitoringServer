import sqlite3
from datetime import datetime
from typing import List, Tuple
import os


class Database:
    def __init__(self, path: str):
        self.path = path
        directory = os.path.dirname(path)

        if not os.path.exists(directory):
            os.makedirs(directory)

        def table_init(_):
            if not self.check_table('hour_avr'):
                self.init_hour_table()
            if not self.check_table('day_avr'):
                self.init_day_table()

        self.execute_sync(table_init)

    def execute_sync(self, func):
        conn = None
        try:
            conn = sqlite3.connect(self.path)
            res = func(conn)
            conn.commit()
            return res
        except Exception as e:
            conn.rollback()
            print(e)
        finally:
            conn.close()

    async def execute(self, func):
        return self.execute_sync(func)

    def check_table(self, table_name: str):
        def query(conn):
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table' and name='"+table_name+"'")
            res = cursor.fetchone()[0]
            if res == 1:
                return True
            else:
                return False

        return self.execute_sync(query)

    def init_hour_table(self):
        def query(conn):
            conn.execute("CREATE TABLE hour_avr(id INTEGER PRIMARY KEY AUTOINCREMENT, time TIMESTAMP,"
                         " left_vib REAL, right_vib REAL, temperature REAL)")

        self.execute_sync(query)

    async def get_all(self):
        def query(conn):
            cur = conn.cursor()
            cur.execute('SELECT time, left_vib, right_vib, temperature FROM hour_avr ORDER BY time')
            return cur.fetchall()

        return await self.execute(query)

    async def get_by_one_day(self, date):
        def query(conn):
            cur = conn.cursor()
            cur.execute('SELECT time, left_vib, right_vib, temperature '
                        'FROM hour_avr WHERE DATE(time) == ? ORDER BY time', (date,))
            return cur.fetchall()

        return await self.execute(query)

    async def get_avr_by_one_day(self, date):
        def query(conn):
            cur = conn.cursor()
            cur.execute('SELECT DATE(time), AVG(left_vib), AVG(right_vib), AVG(temperature) '
                        'FROM hour_avr WHERE DATE(time) == ?', (date,))
            return cur.fetchone()

        return await self.execute(query)

    async def save(self, time, left: float, right: float, temp: float):
        def query(conn):
            cur = conn.cursor()
            cur.execute('INSERT INTO hour_avr(time, left_vib, right_vib, temperature) VALUES (?, ?, ?, ?)'
                        , (time, left, right, temp))

        await self.execute(query)

    async def save_now(self, left, right, temp):
        await self.save(datetime.now(), left, right, temp)

    async def save_many(self, datas: List[Tuple[str, float, float, float]]):
        def query(conn):
            cur = conn.cursor()
            cur.executemany('INSERT INTO hour_avr(time, left_vib, right_vib, temperature) VALUES (?, ?, ?, ?)', datas)

        await self.execute(query)

    def init_day_table(self):
        def query(conn):
            conn.execute("CREATE TABLE day_avr(id INTEGER PRIMARY KEY AUTOINCREMENT, time TIMESTAMP,"
                         " left_vib REAL, right_vib REAL, temperature REAL)")

        self.execute_sync(query)

    async def get_by_duration(self, start, end):
        def query(conn):
            cur = conn.cursor()
            cur.execute('SELECT time, left_vib, right_vib, temperature'
                        ' FROM day_avr WHERE DATE(time) >= ? and DATE(time) <= ? order by time',
                        (start, end))
            return cur.fetchall()

        return await self.execute(query)

    async def save_day_avr(self, time, left, right, temp):
        def query(conn):
            cur = conn.cursor()
            cur.execute('INSERT INTO day_avr(time, left_vib, right_vib, temperature) VALUES (?, ?, ?, ?)'
                        , (time, left, right, temp))

        await self.execute(query)
