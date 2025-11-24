
from enums import AccPointMode
from topology import load_saved_configuration


conf_base = load_saved_configuration(AccPointMode.BASE)
conf_optimal = load_saved_configuration(AccPointMode.OPTIMAL)

print(f"num conf base:{len(conf_base["configurations"])}")
print(f"num conf optimal:{len(conf_optimal["configurations"])}")