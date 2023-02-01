# -*- coding: utf-8 -*-
import torch
from torch import nn
from torch.nn import functional as F
import numpy as np
from typing import List
import easydict
import pickle


class Encoder(nn.Module):
    def __init__(self, input_size=4096, hidden_size=1024, num_layers=2):
        super(Encoder, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True,
                            dropout=0.1, bidirectional=False)

    def forward(self, x):
        outputs, (hidden, cell) = self.lstm(x)  # out: tensor of shape (batch_size, seq_length, hidden_size)
        return hidden, cell


class Decoder(nn.Module):
    def __init__(self, input_size=4096, hidden_size=1024, output_size=4096, num_layers=2):
        super(Decoder, self).__init__()
        self.hidden_size = hidden_size
        self.output_size = output_size
        self.num_layers = num_layers

        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True,
                            dropout=0.1, bidirectional=False)

        self.relu = nn.ReLU()
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x, hidden):
        output, (hidden, cell) = self.lstm(x, hidden)  # out: tensor of shape (batch_size, seq_length, hidden_size)
        prediction = self.fc(output)

        return prediction, (hidden, cell)


class LSTMAutoEncoder(nn.Module):
    def __init__(self,
                 input_dim: int,
                 latent_dim: int,
                 window_size: int = 1,
                 **kwargs) -> None:

        super(LSTMAutoEncoder, self).__init__()

        self.latent_dim = latent_dim
        self.input_dim = input_dim
        self.window_size = window_size

        if "num_layers" in kwargs:
            num_layers = kwargs.pop("num_layers")
        else:
            num_layers = 1

        self.encoder = Encoder(
            input_size=input_dim,
            hidden_size=latent_dim,
            num_layers=num_layers,
        )
        self.reconstruct_decoder = Decoder(
            input_size=input_dim,
            output_size=input_dim,
            hidden_size=latent_dim,
            num_layers=num_layers,
        )

    def forward(self, src: torch.Tensor, **kwargs):
        batch_size, sequence_length, var_length = src.size()

        encoder_hidden = self.encoder(src)

        inv_idx = torch.arange(sequence_length - 1, -1, -1).long()
        reconstruct_output = []
        temp_input = torch.zeros((batch_size, 1, var_length), dtype=torch.float).to(src.device)
        hidden = encoder_hidden
        for t in range(sequence_length):
            temp_input, hidden = self.reconstruct_decoder(temp_input, hidden)
            reconstruct_output.append(temp_input)
        reconstruct_output = torch.cat(reconstruct_output, dim=1)[:, inv_idx, :]

        return [reconstruct_output, src]

    def loss_function(self,
                      *args,
                      **kwargs) -> dict:
        recons = args[0]
        _input = args[1]
        loss = F.mse_loss(recons, _input)
        return loss


class AnomalyCalculator:
    def __init__(self, mean: np.array, std: np.array):
        assert mean.shape[0] == std.shape[0] and mean.shape[0] == std.shape[1], 'warning wrong dimension'
        self.mean = mean
        self.std = std

    def __call__(self, recons_error: np.array):
        x = (recons_error - self.mean)
        return np.matmul(np.matmul(x, self.std), x.T)


class AeModel:
    def __init__(self, model_prt_path: str, calc_path: str):
        self.args = easydict.EasyDict({
            "batch_size": 128,
            "device": torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu'),
            "input_size": 3,
            "latent_size": 1,
            "output_size": 3,
            "window_size": 3,
            "num_layers": 2,
            "learning_rate": 0.001,
            "max_iter": 100000,
            'early_stop': True,
        })
        self.model = LSTMAutoEncoder(input_dim=self.args.input_size, latent_dim=self.args.latent_size,
                                     window_size=self.args.window_size,
                                     num_layers=self.args.num_layers)
        self.model.load_state_dict(torch.load(model_prt_path, map_location=self.args.device))
        self.model.to(self.args.device)
        self.model.eval()
        with open(calc_path, "rb") as fr:
            init_data = pickle.load(fr)
        self.anomaly_calculator = AnomalyCalculator(init_data['mean'], init_data['std'])

    async def inference_model(self, left: List[float], right: List[float], temp: List[float]):
        np_left = np.array(left)
        np_right = np.array(right)
        np_temp = np.array(temp)
        np_arr = np.stack((np_left, np_right, np_temp), axis=1)
        reshaped = np.reshape(np_arr, (128, 3, 3))
        data = torch.from_numpy(reshaped).float()
        res = self.model(data.to(self.args.device))
        return res

    async def get_score(self, predict_values):
        loss_list = []
        with torch.no_grad():
            loss = F.l1_loss(predict_values[0], predict_values[1], reduction='none')
            loss = loss.mean(dim=1).cpu().numpy()
            loss_list.append(loss)

        loss_list = np.concatenate(loss_list, axis=0)
        ans_score = self.anomaly_calculator(loss_list).mean()
        return ans_score


class RegressionModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.linear = nn.Linear(1, 1)

    def forward(self, x):
        return self.linear(x)


class Regression:
    def __init__(self, model_prt_path):
        device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
        self.model = RegressionModel()
        self.model.load_state_dict(torch.load(model_prt_path, map_location=device))
        self.model.to(device)
        self.model.eval()

    async def get_time(self, model_score: float):
        res = self.model(torch.Tensor([model_score]))
        return res


class Model:
    def __init__(self, ae_model_path, calc_data_path, reg_model_path):
        self.ae_model = AeModel(ae_model_path, calc_data_path)
        self.reg_model = Regression(reg_model_path)

    async def get_model_res(self, left: List[float], right: List[float], temp: List[float]):
        model_res = await self.ae_model.inference_model(left, right, temp)
        score = await self.ae_model.get_score(model_res)
        time = await self.reg_model.get_time(score)

        return score, time.item()
