import numpy as np
import pandas as pd


def get_conf_color(conf, min_conf, max_conf):

    conf = min_conf if conf < min_conf else conf
    conf = max_conf if conf > max_conf else conf

    interval_size = (max_conf - min_conf) / 2.0

    colors = np.array([[216, 108, 117], [216, 206, 108], [108, 216, 146]])

    colors = pd.DataFrame(colors, index=[0, 1, 2], columns=['R', 'G', 'B'])

    lower = np.floor((conf - min_conf) / interval_size)
    upper = np.ceil((conf - min_conf) / interval_size)

    pos = (conf - min_conf) / (2.0*interval_size)

    col = (colors.loc[lower] * (1.0 - pos) + colors.loc[upper] * pos).astype(int)

    return '#{:02x}'.format(col.R) + '{:02x}'.format(col.G) + '{:02x}'.format(col.B)
