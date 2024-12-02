import requests

starlink_url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=STARLINK&FORMAT=TLE"
all_active_url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=ACTIVE&FORMAT=TLE"


"""
Cosa fa:
Questo script fa una richiesta al NOMAD per avere tutti i  dati TLE dei satelliti Starlink.
In seguito li salva in un File: ./Data/tle_data.txt
"""


# Posizione di riferimento in latitudine e longitudine (es. Roma)
reference_lat = 41.8967 # latitudine in gradi
reference_lon = 12.4822 # longitudine in gradi
reference_alt = 0       # altitudine in km, considerando l'altitudine del suolo
LEO_ORB = 300           # km
ROMA = (reference_lat, reference_lon, reference_alt)

# Raggio di ricerca in km
radius_km = 300

#Funzione che ritorna i satelliti attivi in formato tle 
def get_active_satellites():
    url = starlink_url
    print("Requesting Data\n")
    response = requests.get(url) # ! Request
    if response.status_code == 200:
        tle_data = response.text.strip().splitlines() # ? TLE
        print("Data received!\n")
        return tle_data
    else:
        print(f"Errore nella richiesta: {response.status_code}")
        return None


def saveTLEOnFile():
    filename="./data/tle_data.txt"
    tle_data = get_active_satellites()
    if tle_data:
        try:
            with open(filename, "w") as file:
                for line in tle_data:
                    file.write(line + "\n")
            print(f"Dati TLE salvati correttamente in '{filename}'")
        except IOError as e:
            print(f"Errore nel salvataggio del file: {e}")
    else:
        print("Nessun dato TLE disponibile per il salvataggio.")

#saveTLEOnFile()
