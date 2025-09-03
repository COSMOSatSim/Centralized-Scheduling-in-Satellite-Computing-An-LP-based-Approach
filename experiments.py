import numpy as np
import random
import json5

# Leggi il file di configurazione JSON
with open('config.json5') as config_file:
    config = json5.load(config_file)

random.seed(config["seed"])


def priority_combination(high, med, low):
    """
        Generate a priority based on the specified weights.

        Parameters:
        - high: High priority.
        - low: Low priority.

        Returns:
        - The generated priority.

        """

    numero_casuale = random.uniform(0, 1)

    if numero_casuale < (high / 100):
        priority_weights = 1  # "alta"
    else:
        priority_weights = 100  # return "bassa"
    return priority_weights


def request_distribution(high, med, low):
    global random_server
    numero_casuale = random.uniform(0, 1)

    if numero_casuale < (high / 100):
        random_server = 1
    elif (high / 100) <= numero_casuale < (high / 100 + med / 100):
        random_server = 3
    elif (high / 100 + med / 100) <= numero_casuale < (1):
        random_server = 8
    return random_server


def generate_random_numbers():
    # Genera 5 numeri casuali non uguali tra 0 e 25
    random_numbers = []
    global random_number
    while len(random_numbers) < 5:
        random_number = random.randint(0, 25)
        if random_number not in random_numbers:
            random_numbers.append(random_number)
    return random_number


# print(random_numbers)

def exponential(description):
    """
    Distribuzione esponenziale con parametro lambda=2.0.
    tasso di arrivo di 2.0 significa che, in media, si verifica
    un evento ogni 0.5 unità di tempo.
    λ = 2.0, è l'inverso del valore atteso (o della media) della distribuzione quindi 1/λ = 0.5 .
    """
    config_arrival_time = config["arrival_time_exponential"]
    arrival_time = np.random.exponential(config_arrival_time)
    # print(f'{description} arrival rate distribution: exponential')
    return arrival_time


def normal(description):
    ## Distribuzione Normale
    # Parametri della distribuzione normale (media e deviazione standard)
    media = 2.0  # Media della distribuzione normale. Tasso medio di arrivo 2 sec
    deviazione_standard = 0.5  # Deviazione standard della distribuzione normale
    arrival_time = np.random.normal(media, deviazione_standard)
    # print(f'{description} arrival rate distribution: normal')
    return arrival_time


def lognormal(description):
    ## Distribuzione Log-Normale
    # Parametri della distribuzione log-normale (media e deviazione standard del logaritmo)
    media_log = 1.0  # Media del logaritmo della distribuzione log-normale
    deviazione_standard_log = 0.2  # Deviazione standard del logaritmo della distribuzione log-normale
    log_arrival_time = np.random.normal(media_log, deviazione_standard_log)
    arrival_time = np.exp(log_arrival_time)

    # print(f'{description} arrival rate distribution: log-normal')
    return arrival_time


def weibull(description):
    """
    Distribuzione Weibull
    Parametri della distribuzione Weibull (forma e scala)

    Parametri:
        - shape: Parametro di forma della distribuzione Weibull
        - scale: tasso medio di arrivo 1/scale = 1/2 = 0,5
    """
    shape = 2.0
    scale = 2.0

    # Genera campioni da una distribuzione Weibull
    arrival_time = np.random.weibull(shape) * scale

    # print(f'{description} arrival rate distribution: Weibull')
    return arrival_time


# Genera un numero con distribuzione esponenziale troncata tra 10 e 25 minuti
def truncated_exponential(mean, lower, upper):
    return np.random.exponential(scale=mean)
    ''' while True:
        value = np.random.exponential(scale=mean)
        if lower <= value <= upper:
            return value
'''