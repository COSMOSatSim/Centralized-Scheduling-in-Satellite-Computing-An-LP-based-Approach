import json
from math import sqrt
import numpy as np
import sys
from datetime import timedelta
from skyfield.api import load, EarthSatellite, Topos, wgs84


with open('config.json') as config_file:
    config = json.load(config_file)

ts = load.timescale()                                   # ts : time management with astronomical time
time_now = ts.now()


# reading TLE DATA from File
def loadTLEFromFile(filename):
    try:
        with open(filename, "r") as file:
            tle_data = file.read().splitlines()
        print(f"Dati TLE caricati correttamente da {filename}")
        return tle_data
    except FileNotFoundError:
        print(f"Errore: il file {filename} non è stato trovato.")
        return None
    except IOError as e:
        print(f"Errore nella lettura del file: {e}")
        return None

TLE_DATA = loadTLEFromFile("./data/tle_data.txt")       # Load TLE Data 
# ---------------------------------------------------------------------------- #
#                                    Printer                                   #
# ---------------------------------------------------------------------------- #

def printSatList(*sats):
    for l in sats:
        print("-"*20)
        [print(f"SATELLITE: {s[0].name} Distance: {s[1]}") for s in l]


# ---------------------------------------------------------------------------- #
#                                    Getter                                    #
# ---------------------------------------------------------------------------- #

def get_current_time():
    """
    Get the current time using Skyfield's timescale.

    This function loads the timescale from the Skyfield library and returns the current time.

    Returns:
        skyfield.timelib.Time: The current time according to Skyfield's timescale.
    """
    ts = load.timescale()  # Carica la scala temporale di Skyfield
    return ts.now()   

# Getter reference system from a Satellite 
def getSystemFromSat(satellite, Geocentric = False, time = time_now):
    """
    Get the reference system from a satellite.

    Args:
        satellite (EarthSatellite): The satellite object.
        Geocentric (bool): If False, return the system relative to the observer's point of view.
                           If True, return the satellite's position relative to the center of the Earth (Geocentric).
        time (Time): The time at which to get the satellite's position.
    Returns:
        Geocentric or Topocentric: The reference system of the satellite at the given time.
    """
    if Geocentric : # Satellite Position from the Center of Earth
        return satellite.at(time)                   # return geocentric system  
    else:           # Satellite Position from the Observer Position
        difference = satellite - getObserverObj()   # Calculate the difference between the satellite's position and the observer's position to get the topocentric reference system
        return difference.at(time)                  # return topocentric system
    

# Getter Topos 'Observer' object 
def getObserverObj(lat = config["location"]["Roma"]["lat"], lon = config["location"]["Roma"]["lat"]):
    return Topos( lat, lon)  


def get_orbit_proximity(sat1 , sat2, t):
    """
    Calculates the distance between two satellites in kilometers.

    Args:
        satellite1: EarthSatellite object representing the first satellite.
        satellite2: EarthSatellite object representing the second satellite.
        timestamp: Skyfield Time object representing the moment of calculation.

    Returns: The distance between the two satellites in kilometers.
    """
    # Get geocentric positions in km
    pos_sat1 = getSystemFromSat(sat1, True, t).position.km
    pos_sat2 = getSystemFromSat(sat2, True, t).position.km

    # Extraction of coordinate components
    x1, y1, z1 = pos_sat1
    x2, y2, z2 = pos_sat2

    return sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)     # Calculate the Euclidean distance

def are_satellites_equal(sat1, sat2):
    """
    Compare two satellites to check if they are the same based on their name and satellite number.

    Args:
        sat1: EarthSatellite object representing the first satellite.
        sat2: EarthSatellite object representing the second satellite.

    Returns:
        bool: True if the satellites are the same, False otherwise.
    """
    # Confronta per nome e numero satnum
    return (
        sat1.name == sat2.name and
        sat1.model.satnum == sat2.model.satnum
    )

def getLatency(distance:float):
    LIGHT_SPEED = 299792458  #m/s
    # convert distance to meters
    distance_m = distance * 1000

    return distance_m / LIGHT_SPEED  # Calculate latency in seconds

# ---------------------------------------------------------------------------- #
#                                    Filter                                    #
# ---------------------------------------------------------------------------- #

def filterSatellitesInView(satellite):
    """
    Input: Satellites
    Output: Boolean value | True : sat is coming in our direction
                          | False : sat is not coming in our direction
    """
    sys = getSystemFromSat(satellite) 
    
    velocity = sys.velocity    

    r = sys.position.km                             # r è la posizione relativa del SAT rispetto all'observer
    r_unit = r / np.linalg.norm(r)                  # Vettore unitario 
    v_rel = np.dot(velocity.km_per_s, r_unit)       # Calcoliamo la velocità calcolando il prodotto scalare tra r e r_unit
    
    return True if v_rel < 0 else False

# ---------------------------------------------------------------------------- #
def getAllSatOnMe(Phi_max = config["Phi_max"], time = time_now, Num_Access_point = config["access_point"]):    
    
    buffer_Phi = Phi_max - config["Phi_buffer"]             # Angle of a Buffer Zone
    satellites_dome, satellites_buffer = [], []             
    tle_data = TLE_DATA

    # Prendo tutti i satelliti nella mia Cupola e BufferZone
    for i in range(0, len(tle_data), 3):
        name = tle_data[i].strip()
        line1 = tle_data[i + 1].strip()
        line2 = tle_data[i + 2].strip()

        satellite = EarthSatellite(line1, line2, name, ts)  # Converting tle Data in SGP4 Satellite Object
        sys = getSystemFromSat(satellite, time = time)      # reference system 
        
        alt, az, distance = sys.altaz()                     # alt : Altitude in degrees relative to the observer
                                                            # az : Sat Azimuth Angle relative to the observer
                                                            # distance: distance Sat - Observer
        if alt.degrees > buffer_Phi:
            if alt.degrees > Phi_max:
                satellites_dome.append((satellite, distance.km))
            else:
                # Controllo che stia venendo nella mia direzione
                if filterSatellitesInView(satellite):
                    satellites_buffer.append((satellite, distance.km))

    #Ordino i satelliti in base alla posizione rispetto all'utente
    sat_sort_dome, sat_sort_buff = sorted(satellites_dome, key=lambda x: x[1]), sorted(satellites_buffer, key=lambda x: x[1])
    
    #Determino Access Points
    counter, acc_points, dome = 0, [], []
    for s in sat_sort_dome:
        if counter < Num_Access_point and filterSatellitesInView(s[0]):
            acc_points.append((s[0], s[1]))
            counter+=1
        else:
            dome.append((s[0], s[1]))
    
    return acc_points, dome, sat_sort_buff


def classifySat_BufferZone(buffer_satellites, time = time_now):
    time_end = ts.utc(time.utc_datetime() + timedelta(minutes=40))
    selected_satellites = []

    min_elev_cone = 90 - config["Phi_max"]   # Quantità di gradi al di sotto della soglia dove osservo.
    buffer_Phi = config["Phi_max"] - config["Phi_buffer"]             # Angle of a Buffer Zone

    for s in buffer_satellites:
        # Calcolo eventi di passaggio
        t, events = s[0].find_events(getObserverObj(), time, time_end, altitude_degrees=buffer_Phi)
        max_elevation = 0                   # ? Masimo punto di elevazione del satellite

        for ti, event in zip(t, events):
            if event == 1:  # Max Alt

                syst = getSystemFromSat(s[0], time = time)      # reference system 
                alt, az, distance = syst.altaz() 

                max_elevation = alt.degrees  # Elevazione in gradi
                break
        print(f"SAT: {s[0].name} - Elevation: {max_elevation} >= {min_elev_cone}") 
        # Verifica se il satellite raggiunge almeno la soglia del cono di osservazione
        if max_elevation >= min_elev_cone :
            selected_satellites.append((s[0], s[1], max_elevation))
    
    return selected_satellites






# ---------------------------------------------------------------------------- #

def check_satellite_visibility(satellite, location, start, end):
    # Intervallo di tempo con step di 1 minuto
    times = ts.utc_range(start.utc_datetime(), end.utc_datetime(), timedelta(minutes=1))
    
    # Trova elevazioni per ogni punto temporale
    elevations = []
    for t in times:
        difference = satellite - location
        topocentric = difference.at(t)
        alt, _, _ = topocentric.altaz()
        elevations.append((t, alt.degrees))
    
    # Filtra le elevazioni tra 20° e 40° e verifica se superano i 40°
    between_20_40 = any(20 <= alt <= 40 for _, alt in elevations)
    exceeds_40 = any(alt > 40 for _, alt in elevations)
    
    return between_20_40 and exceeds_40

def checkConsistency():
    tle_data = TLE_DATA
    satellites = []
    t0 = time_now

    location = wgs84.latlon(41.9028, 12.4964)  # Roma


    #Genero la lista di Satelliti
    for i in range(0, len(tle_data), 3):
        name = tle_data[i].strip()
        line1 = tle_data[i + 1].strip()
        line2 = tle_data[i + 2].strip()

        satellite = EarthSatellite(line1, line2, name, ts)
        # TODO ricordati di effettuare il controllo della consistenza

    