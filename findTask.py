import csv

def find_next_integer_in_csv(file_path):
    current_integer = 1

    while True:
        found = False
        with open(file_path, mode='r') as file:
            csv_reader = csv.reader(file)
            for row in csv_reader:
                if row and row[0].isdigit() and int(row[0]) == current_integer:
                    found = True
                    current_integer += 1
                    break
        if not found:
            return current_integer

file_path = 'OrbitAware_simulation result-open-System_AP5_0.5-1.5/simulation result_RR_request_distribution_latency_0.007_distribuited/42/simulation_results_20_0_80_exponential_42_0.2.csv'
result = find_next_integer_in_csv(file_path)
print(f"The next integer not found in the CSV is: {result}")