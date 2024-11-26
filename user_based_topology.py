import json
from math import sqrt
from skyfield.api import load, EarthSatellite, Topos
from matplotlib.animation import FuncAnimation




with open('./data/config.json') as config_file:
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
# ---------------------------------------------------------------------------- #
#                                   Plotters                                   #
# ---------------------------------------------------------------------------- #
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import numpy as np

def plot_satellites_3d(satellites, ts):
    """
    Rappresenta una lista di satelliti nello spazio 3D con i nomi e linee che collegano ciascun satellite
    al primo della lista.

    :param satellites: Lista di oggetti EarthSatellite.
    :param ts: Oggetto time per calcolare la posizione dei satelliti.
    """
    # Estrai le coordinate 3D dei satelliti
    positions = [sat[0].at(ts).position.km for sat in satellites]
    names = [sat[0].name for sat in satellites]

    # Estrai le coordinate X, Y, Z
    x_coords = [pos[0] for pos in positions]
    y_coords = [pos[1] for pos in positions]
    z_coords = [pos[2] for pos in positions]

    # Creazione della figura 3D
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')

    # Traccia i punti dei satelliti
    ax.scatter(x_coords, y_coords, z_coords, color='blue', label='Satelliti')

    # Aggiungi i nomi dei satelliti accanto ai punti
    for x, y, z, name in zip(x_coords, y_coords, z_coords, names):
        ax.text(x, y, z, name, color='red')

    # Disegna linee tra il primo satellite e tutti gli altri
    ref_x, ref_y, ref_z = x_coords[0], y_coords[0], z_coords[0]
    for x, y, z in zip(x_coords[1:], y_coords[1:], z_coords[1:]):
        ax.plot([ref_x, x], [ref_y, y], [ref_z, z], color='green', linestyle='--')

    # Etichette degli assi
    ax.set_xlabel("X (km)")
    ax.set_ylabel("Y (km)")
    ax.set_zlabel("Z (km)")
    ax.set_title("Posizioni dei satelliti in 3D")

    # Mostra il grafico
    plt.legend()
    plt.show()


def plot_satellites_3d_with_point(satellites, ts, lat = config["location"]["Roma"]["lat"], lon = config["location"]["Roma"]["lon"], earth_radius=6371):
    """
    Rappresenta una lista di satelliti nello spazio 3D con i nomi e un punto rosso sulla Terra dato da latitudine e longitudine.
    Collega ciascun satellite al primo satellite della lista.

    :param satellites: Lista di oggetti EarthSatellite.
    :param ts: Oggetto time per calcolare la posizione dei satelliti.
    :param lat: Latitudine del punto terrestre (in gradi).
    :param lon: Longitudine del punto terrestre (in gradi).
    :param earth_radius: Raggio medio terrestre (in km). Default: 6371 km.
    """
    # Converti latitudine e longitudine in coordinate cartesiane
    lat_rad = np.radians(lat)
    lon_rad = np.radians(lon)
    point_x = earth_radius * np.cos(lat_rad) * np.cos(lon_rad)
    point_y = earth_radius * np.cos(lat_rad) * np.sin(lon_rad)
    point_z = earth_radius * np.sin(lat_rad)

    # Estrai le coordinate 3D dei satelliti
    positions = [sat[0].at(ts).position.km for sat in satellites]
    names = [sat[0].name for sat in satellites]

    # Estrai le coordinate X, Y, Z
    x_coords = [pos[0] for pos in positions]
    y_coords = [pos[1] for pos in positions]
    z_coords = [pos[2] for pos in positions]

    # Creazione della figura 3D
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')

    # Traccia i punti dei satelliti
    ax.scatter(x_coords, y_coords, z_coords, color='blue', label='Satelliti')

    # Aggiungi i nomi dei satelliti accanto ai punti
    for x, y, z, name in zip(x_coords, y_coords, z_coords, names):
        ax.text(x, y, z, name, color='red')

    # Disegna linee tra il primo satellite e tutti gli altri
    ref_x, ref_y, ref_z = x_coords[0], y_coords[0], z_coords[0]
    for x, y, z in zip(x_coords[1:], y_coords[1:], z_coords[1:]):
        ax.plot([ref_x, x], [ref_y, y], [ref_z, z], color='green', linestyle='--')

    # Aggiungi il punto terrestre (rosso)
    ax.scatter(point_x, point_y, point_z, color='red', s=100, label='Punto terrestre')
    ax.text(point_x, point_y, point_z, "Location", color='black')

    # Etichette degli assi
    ax.set_xlabel("X (km)")
    ax.set_ylabel("Y (km)")
    ax.set_zlabel("Z (km)")
    ax.set_title("Posizioni dei satelliti in 3D e punto terrestre")

    # Mostra la legenda
    plt.legend()
    plt.show()


def plot_satellites_with_distances(satellite_tuples, ts, lat = config["location"]["Roma"]["lat"], lon = config["location"]["Roma"]["lon"], earth_radius=6371):
    """
    Rappresenta i satelliti in uno spazio 3D con linee che collegano i satelliti tra loro e al punto terrestre specificato.

    :param satellite_tuples: Lista di tuple con il formato:
        (EarthSatellite, distanza_terra, distanza_altri_satelliti).
    :param lat: Latitudine del punto terrestre (in gradi).
    :param lon: Longitudine del punto terrestre (in gradi).
    :param earth_radius: Raggio medio terrestre (in km). Default: 6371 km.
    """
    # Converti latitudine/longitudine del punto terrestre in coordinate cartesiane
    lat_rad = np.radians(lat)
    lon_rad = np.radians(lon)
    point_x = earth_radius * np.cos(lat_rad) * np.cos(lon_rad)
    point_y = earth_radius * np.cos(lat_rad) * np.sin(lon_rad)
    point_z = earth_radius * np.sin(lat_rad)

    # Estrai i dati dalle tuple
    satellites = [sat[0] for sat in satellite_tuples]
    distances_to_point = [sat[1] for sat in satellite_tuples]
    distances_between_satellites = [sat[2] for sat in satellite_tuples]

    # Calcola le posizioni 3D dei satelliti
    positions = [sat.at(ts).position.km for sat in satellites]
    names = [sat.name for sat in satellites]

    # Estrai le coordinate X, Y, Z
    x_coords = [pos[0] for pos in positions]
    y_coords = [pos[1] for pos in positions]
    z_coords = [pos[2] for pos in positions]

    # Creazione della figura 3D
    fig = plt.figure(figsize=(12, 9))
    ax = fig.add_subplot(111, projection='3d')

    # Traccia i punti dei satelliti
    ax.scatter(x_coords, y_coords, z_coords, color='blue', label='Satelliti')

    # Aggiungi i nomi dei satelliti accanto ai punti
    for x, y, z, name in zip(x_coords, y_coords, z_coords, names):
        ax.text(x, y, z, name, color='red')

    # Disegna linee gialle tra ogni satellite e il punto terrestre
    for x, y, z, distance in zip(x_coords, y_coords, z_coords, distances_to_point):
        ax.plot([x, point_x], [y, point_y], [z, point_z], color='yellow', linestyle='--')
        # Aggiungi l'etichetta della distanza
        mid_x, mid_y, mid_z = (x + point_x) / 2, (y + point_y) / 2, (z + point_z) / 2
        ax.text(mid_x, mid_y, mid_z, f"{distance:.2f} km", color='orange')

    # Disegna linee verdi tra il primo satellite e tutti gli altri
    ref_x, ref_y, ref_z = x_coords[0], y_coords[0], z_coords[0]
    for x, y, z, distance in zip(x_coords[1:], y_coords[1:], z_coords[1:], distances_between_satellites[1:]):
        ax.plot([ref_x, x], [ref_y, y], [ref_z, z], color='green', linestyle='--')
        # Aggiungi l'etichetta della distanza
        mid_x, mid_y, mid_z = (ref_x + x) / 2, (ref_y + y) / 2, (ref_z + z) / 2
        ax.text(mid_x, mid_y, mid_z, f"{distance:.2f} km", color='green')

    # Aggiungi il punto terrestre (rosso)
    ax.scatter(point_x, point_y, point_z, color='red', s=100, label='Punto terrestre')
    ax.text(point_x, point_y, point_z, "Location", color='black')

    # Etichette degli assi
    ax.set_xlabel("X (km)")
    ax.set_ylabel("Y (km)")
    ax.set_zlabel("Z (km)")
    ax.set_title("Posizioni dei satelliti in 3D con distanze")

    # Mostra la legenda
    plt.legend()
    plt.show()

# Funzione per animare i satelliti
def animate_satellites_from_tuples(satellite_states, lat=config["location"]["Roma"]["lat"], lon=config["location"]["Roma"]["lon"], earth_radius=6371):
    """
    Anima il movimento dei satelliti basato su una lista di liste di tuple.

    :param satellite_states: Lista di liste, dove ogni sotto-lista rappresenta lo stato dei satelliti a un dato momento.
                             Ogni tupla contiene (nome_satellite, (x, y, z)).
    :param lat: Latitudine del punto terrestre (in gradi).
    :param lon: Longitudine del punto terrestre (in gradi).
    :param earth_radius: Raggio medio terrestre (in km). Default: 6371 km.
    """
    # Converti latitudine e longitudine in coordinate cartesiane
    lat_rad = np.radians(lat)
    lon_rad = np.radians(lon)
    point_x = earth_radius * np.cos(lat_rad) * np.cos(lon_rad)
    point_y = earth_radius * np.cos(lat_rad) * np.sin(lon_rad)
    point_z = earth_radius * np.sin(lat_rad)

    # Creazione della figura 3D
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')

    # Punto terrestre
    ax.scatter(point_x, point_y, point_z, color='red', s=100, label='Punto terrestre')
    ax.text(point_x, point_y, point_z, "Location", color='black')

    # Imposta i limiti
    ax.set_xlim([-earth_radius * 2, earth_radius * 2])
    ax.set_ylim([-earth_radius * 2, earth_radius * 2])
    ax.set_zlim([-earth_radius * 2, earth_radius * 2])
    ax.set_xlabel("X (km)")
    ax.set_ylabel("Y (km)")
    ax.set_zlabel("Z (km)")
    ax.set_title("Animazione satelliti in 3D")

    # Inizializza gli elementi dell'animazione
    scatter = ax.scatter([], [], [], color='blue', label='Satelliti')
    text_annotations = []

    # Funzione di aggiornamento per l'animazione
    def update(frame):
        nonlocal text_annotations

        # Cancella le annotazioni esistenti
        for annotation in text_annotations:
            annotation.remove()
        text_annotations.clear()

        # Ottieni lo stato dei satelliti al frame corrente
        current_state = satellite_states[frame]

        # Estrai posizioni e nomi
        x_coords = [sat[1][0] for sat in current_state]
        y_coords = [sat[1][1] for sat in current_state]
        z_coords = [sat[1][2] for sat in current_state]
        names = [sat[0] for sat in current_state]

        # Aggiorna il grafico
        scatter._offsets3d = (x_coords, y_coords, z_coords)

        # Aggiungi i nomi dei satelliti
        for x, y, z, name in zip(x_coords, y_coords, z_coords, names):
            text = ax.text(x, y, z, name, color='red')
            text_annotations.append(text)

        return scatter,

    # Creazione animazione
    ani = FuncAnimation(fig, update, frames=len(satellite_states), interval=500, blit=False)

    plt.legend()
    plt.show()


# ---------------------------------------------------------------------------- #
#                                    Getter                                    #
# ---------------------------------------------------------------------------- #

# Getter reference system from a Satellite 
def getSystemFromSat(satellite, Geocentric = False, time = time_now):
    """
    Geocentric = False, we want to return the system relative to the observer's point of view; 
    otherwise, if Geocentric = True, we return the system relative to the center of the Earth.
    """

    if Geocentric : # Satellite Position from the Center of Earth
        return satellite.at(time)                   # return geocentric system  
    else:           # Satellite Position from the Observer Position
        difference = satellite - getObserverObj()   # Change the reference system from ⁡⁢⁢⁢Geocentric⁡ to ⁡⁢⁣⁢Topocentric⁡
        return difference.at(time)                  # return topocentric system
    

# Getter Topos 'Observer' object 
def getObserverObj(lat = config["location"]["Roma"]["lat"], lon = config["location"]["Roma"]["lat"]):
    return Topos( lat, lon)  


# Get the distance between two satellites in a certain time
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

def get_distance_from_Access_Point(sorted_sat, t = time_now):
    sat_distance_vector = [(sorted_sat[0][0], sorted_sat[0][1].km, 0)]         # The first element is always 0. Because it is the distance from Sat 0 (closest to the user) compared to the other satellites around
    for i in range(1, len(sorted_sat)-1):
        sat_distance_vector.append((sorted_sat[i][0], sorted_sat[i][1].km, get_orbit_proximity(sorted_sat[0][0], sorted_sat[i][0], t)))
    sat_distance_vector_sorted = sorted(sat_distance_vector, key=lambda x: x[2])
    print(sat_distance_vector_sorted)
    return sat_distance_vector_sorted



def getSatOnMe(Phi_max = config["Phi_max"], time = time_now):
    """
    Input: Phi_max angolo di ascolto dell'osservatore
    Output: Tutti i Sat che sono all'interno del cono costruito rispetto alla Phi_max e alla posizione dell'observer
    """
    satellites, animation_satellite_list = [], []
    
    tle_data = loadTLEFromFile("./data/tle_data.txt")       # Load TLE Data 

    for i in range(0, len(tle_data), 3):
        name = tle_data[i].strip()
        line1 = tle_data[i + 1].strip()
        line2 = tle_data[i + 2].strip()

        satellite = EarthSatellite(line1, line2, name, ts)  # Converting tle Data in SGP4 Satellite Object
        sys = getSystemFromSat(satellite, time = time)      # reference system 
        
        alt, az, distance = sys.altaz()                     # alt : Altitude in degrees relative to the observer
                                                            # az : Sat Azimuth Angle relative to the observer
                                                            # distance: distance Sat - Observer
        if alt.degrees > Phi_max:
            x, y, z = sys.position.km                          # Position in km
            animation_satellite_list.append((name, (x, y, z)))  # Save coordinate for animation

            satellites.append((satellite, distance))
            #print(f"{name} - {distance.km} - POS: {position}\n")
    
    return sorted(satellites, key=lambda x: x[1].km), animation_satellite_list


def buildTopology(sat_ordered):
    biDim_Topology = []                                 # Bidimensional Topology
    for s in sat_ordered:
        if s[2] <= config["Laser_Comunication_Range"] : # Check laser distance 
            biDim_Topology.append((s[0], s[2]))         # (Sat info, Sat distance from Access Point)
        else:
            break
    return biDim_Topology


def makeTopology(time = time_now):
    closerSatellite_Sorted, biDim_Topology_Animation = getSatOnMe(time = time)
    sat_distance_vector_sorted_from_access_point = get_distance_from_Access_Point(closerSatellite_Sorted, time)
    [print("    SAT:"+str(element[0])+"      Dist from Acc_Point: "+str(element[2])) for element in sat_distance_vector_sorted_from_access_point]
    print("-------------------------------------------------------------------------------------------------------\n")

    #plot_satellites_3d(closerSatellite_Sorted, time_now)                                       # ! Plot SAT in the Sky
    #plot_satellites_3d_with_point(closerSatellite_Sorted, time_now)                            # ! Plot Sat in the Sky, Rome, line between all Sat and the "Access poing"
    #plot_satellites_with_distances(sat_distance_vector_sorted_from_access_point, time_now)     # ! Plot Sat in the Sky, Rome, line between all Sat and the "Access poing" and line between all Sat and Location

    return buildTopology(sat_distance_vector_sorted_from_access_point), biDim_Topology_Animation   # Bidimensional Topology


def generate_topology_over_time(delta_minutes):
    """
    Scorre ogni secondo da t=0 fino a delta_t minuti nel futuro,
    richiamando `makeTopology` per ciascun secondo.

    :param delta_minutes: Intervallo di tempo in minuti.
    """
    ts = load.timescale()
    time_now = ts.now()
    triDim_Topology, triDim_Topology_Animation = [], [] 
    
    # Calcola il tempo finale (tempo attuale + delta_minutes)
    future_time = ts.utc(
        time_now.utc.year, time_now.utc.month, time_now.utc.day,
        time_now.utc.hour, time_now.utc.minute + delta_minutes, time_now.utc.second
    )
    
    # Scorrere tutti i secondi da t=0 fino a future_time
    current_time = time_now
    while current_time < future_time:
        #print(f"Current time: {current_time.utc_datetime()}")  # Debug
        biDim_Top, biDim_Top_Anim = makeTopology(time=current_time)
        triDim_Topology.append(biDim_Top)
        triDim_Topology_Animation.append(biDim_Top_Anim)
        
        # Incrementa di 1 secondo
        current_time = ts.utc(
            current_time.utc.year, current_time.utc.month, current_time.utc.day,
            current_time.utc.hour, current_time.utc.minute, current_time.utc.second + 1
        )
    #print(triDim_Topology)
    #print("----------------------------------------------------------------------------------------------\n\n")
    #print(triDim_Topology_Animation)
    animate_satellites_from_tuples(triDim_Topology_Animation)



# ---------------------------------------------------------------------------- #
#                                     TEST                                     #
# ---------------------------------------------------------------------------- #
#makeTopology()
generate_topology_over_time(1)  # ! 1 minuti di simulazione