from csvController import CsvController


class RawdataController:
    def __init__(self, raw_directory, external_directory):
        self.vib_csv = CsvController(directory=raw_directory,
                                     device_name='vib',
                                     header=['time', 'machine1_left', 'machine1_right', 'machine2_left', 'machine2_right'],
                                     external_directory=external_directory)

        self.temp_csv = CsvController(directory=raw_directory,
                                      device_name='temp',
                                      header=['time', 'machine1', 'machine2'],
                                      external_directory=external_directory)

    async def add_vib(self, message: dict):
        machine1_left = message['machine1_left']
        machine1_right = message['machine1_right']
        machine2_left = message['machine2_left']
        machine2_right = message['machine2_right']

        await self.vib_csv.add_data([[message['time'] for _ in range(len(message['machine1_left']))],
                                     machine1_left, machine1_right, machine2_left, machine2_right])

    async def add_temp(self, message: dict):
        machine1 = message['machine1']
        machine2 = message['machine2']

        await self.temp_csv.add_data([[message['time'] for _ in range(len(message['machine1']))],
                                      machine1, machine2])
