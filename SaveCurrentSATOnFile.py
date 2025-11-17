import requests

from enums import tle_data

starlink_url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=STARLINK&FORMAT=TLE"
all_active_url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=ACTIVE&FORMAT=TLE"


"""
Cosa fa:
Questo script fa una richiesta al NOMAD per avere tutti i  dati TLE dei satelliti Starlink.
In seguito li salva in un File: ./Data/tle_data.txt
"""

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


def saveTLEOnFile() -> tle_data:
    filename="./data/tle_data.txt"
    tle_data = get_active_satellites()
    
    if tle_data:
        try:
            with open(filename, "w") as file:
                for line in tle_data:
                    file.write(line + "\n")
            print(f"Dati TLE salvati correttamente in '{filename}'")
            return tle_data
        except IOError as e:
            print(f"Errore nel salvataggio del file: {e}")
    else:
        print("Nessun dato TLE disponibile per il salvataggio.")

