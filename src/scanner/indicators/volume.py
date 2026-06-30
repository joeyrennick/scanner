def add_volume_indicators(data, window=20):
    data = data.copy()

    volume = data["Volume"]

    if hasattr(volume, "columns"):
        volume = volume.iloc[:, 0]

    data["AvgVolume20"] = volume.rolling(window=window).mean()
    data["RelativeVolume"] = volume / data["AvgVolume20"]

    return data