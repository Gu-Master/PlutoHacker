import numpy as np


def normalized_haar_wavelet(omega, scale):
    omega_cpy = omega[:] / scale
    omega_cpy[0] = 1.0  # first element always zero, so prevent division by zero later

    result = (1j * np.square(-1 + np.exp(0.5j * omega))) / omega_cpy
    return result


def cwt_haar(x: np.ndarray, scale=10):
    """
    continuous haar wavelet transform based on the paper
    "A practical guide to wavelet analysis" by Christopher Torrence and Gilbert P Compo

    """
    next_power_two = 2 ** int(np.log2(len(x)))

    x = x[0:next_power_two]
    num_data = len(x)

    # get FFT of x (eq. (3) in paper)
    x_hat = np.fft.fft(x)

    # Get omega (eq. (5) in paper)
    f = 2.0 * np.pi / num_data
    omega = f * np.concatenate(
        (np.arange(0, num_data // 2), np.arange(num_data // 2, num_data) * -1)
    )

    # get psi hat (eq. (6) in paper)
    psi_hat = np.sqrt(2.0 * np.pi * scale) * normalized_haar_wavelet(
        scale * omega, scale
    )

    # get W (eq. (4) in paper)
    W = np.fft.ifft(x_hat * psi_hat)

    return W[2 * scale : -2 * scale]
