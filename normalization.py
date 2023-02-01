import pickle


async def norm(data, mean, std):
    return (data - mean) / std


class Normalization:
    def __init__(self, data_path):
        with open(data_path, "rb") as fr:
            data = pickle.load(fr)
            mean = data['mean']
            self.mean_temp = mean[0]
            self.mean_left = mean[1]
            self.mean_right = mean[2]

            std = data['std']
            self.std_temp = std[0]
            self.std_left = std[1]
            self.std_right = std[2]

    async def norm(self, left, right, temp):
        norm_left = await norm(left, self.mean_left, self.std_left)
        norm_right = await norm(right, self.mean_right, self.std_right)
        norm_temp = await norm(temp, self.mean_temp, self.std_temp)

        return norm_left, norm_right, norm_temp

