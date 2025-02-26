import os
import pandas as pd
import matplotlib.pyplot as plt
import json

# Get the current directory path
current_directory = os.path.dirname(os.path.abspath(__file__))
def process_directory(directory):
    all_dataframes = []  # List to store DataFrames from all files
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if filename.startswith("boxplot_data_"):
                file_path = os.path.join(root, filename)
                # Read the file into a DataFrame
                df = pd.read_csv(file_path)
                all_dataframes.append(df)  # Append the DataFrame to the list

    if not all_dataframes:
        print(f"No data files found in {directory}")
        return None

    pd.set_option('display.max_columns', None)  # Show all columns
    pd.set_option('display.expand_frame_repr', False)  # Do not wrap rows
    combined_df = pd.concat(all_dataframes, ignore_index=True)

    # Save combined DataFrame to CSV
    combined_df.to_csv('combined_data.csv', index=False)

    return combined_df


# Function to plot data
def plot_data(dataframe, priority):
    unique_rates = dataframe["Arrival Rate"].unique()

    # Crea una figura e un asse comuni per tutte le Arrival Rate
    fig, ax = plt.subplots(figsize=(10, 6))

    for rate in unique_rates:
        print(f"Plotting rate {rate}")
        subset_df = dataframe[dataframe["Arrival Rate"] == rate].copy()

        # Assicurati che la colonna 'AP' sia numerica
        subset_df['AP'] = pd.to_numeric(subset_df['AP'], errors='coerce')

        pivot_df = subset_df.pivot_table(
            index=['Typology', 'Arrival Rate'],
            columns='AP',
            values='Mean',
            aggfunc='first'
        ).reset_index()

        print("Pivot table columns before renaming:", pivot_df.columns.tolist())

        # Mappa i valori di AP alle nuove etichette
        new_column_names = {5: 1, 10: 2, 15: 3, 20: 4}
        pivot_df = pivot_df.rename(columns=new_column_names)
        print("Pivot table columns after renaming:", pivot_df.columns.tolist())

        # Seleziona solo le colonne di interesse
        expected_cols = ['Typology', 1, 2, 3, 4]
        available_cols = [col for col in expected_cols if col in pivot_df.columns]
        if len(available_cols) != len(expected_cols):
            print("Warning: Missing expected columns. Available columns:", pivot_df.columns.tolist())
        plot_df = pivot_df[available_cols]

        # Aggiungi una linea per ogni combinazione di Typology e Arrival Rate
        for (typology), group in plot_df.groupby("Typology"):
            # Scegli un marker in base alla typology
            marker = 'o' if typology == "centralized" else '*'
            # Il label include sia la Typology che il valore di Arrival Rate per distinguerle
            ax.plot(group.columns[1:], group.iloc[0, 1:], marker=marker,
                    label=f"{typology} - AR {rate} - AVG")

    # Imposta etichette e ticks degli assi
    ax.set_xlabel("AP", fontsize=20)
    ax.set_xticks([1, 2, 3, 4])
    ax.set_xticklabels(["5", "10", "15", "20"])
    if priority == "High":
        ax.set_yticks([0,5,10,15,20,25])
    else:
        ax.set_yticks([0,5,10,15,20,25])
    ax.set_ylabel("Response time (sec)", fontsize=20)
    ax.tick_params(axis='both', which='major', labelsize=20)
    ax.legend(fontsize=20)

    # Imposta i limiti degli assi (opzionale, se necessario)
    ax.set_xlim(ax.get_xlim())
    ax.set_ylim(ax.get_ylim())

    plt.tight_layout()
    plots_directory = os.path.join(current_directory, 'merged graph AP-AVG')
    print("Saving plot to:", plots_directory)
    os.makedirs(plots_directory, exist_ok=True)
    plt.savefig(os.path.join(plots_directory, f"Mean vs Arrival Rate - {priority} Priority - ALL Arrival Rates.png"), dpi=300, bbox_inches='tight')
    plt.show()


'''
#PER I SINGOLI PLOT
def plot_data(dataframe, priority):
    unique_rates = dataframe["Arrival Rate"].unique()

    for rate in unique_rates:
        print(f"Plotting rate {rate}")
        subset_df = dataframe[dataframe["Arrival Rate"] == rate].copy()

        # Ensure 'AP' is numeric
        subset_df['AP'] = pd.to_numeric(subset_df['AP'], errors='coerce')

        pivot_df = subset_df.pivot_table(
            index=['Typology', 'Arrival Rate'],
            columns='AP',
            values='Mean',
            aggfunc='first'
        ).reset_index()

        print("Pivot table columns before renaming:", pivot_df.columns.tolist())

        # Adjust renaming mapping if necessary; if AP values are numeric
        new_column_names = {5: 1, 10: 2, 15: 3, 20: 4}
        pivot_df = pivot_df.rename(columns=new_column_names)
        print("Pivot table columns after renaming:", pivot_df.columns.tolist())

        # Select only the columns that exist
        expected_cols = ['Typology', 1, 2, 3, 4]
        available_cols = [col for col in expected_cols if col in pivot_df.columns]
        if len(available_cols) != len(expected_cols):
            print("Warning: Missing expected columns. Available columns:", pivot_df.columns.tolist())
        plot_df = pivot_df[available_cols]

        # Plot the data
        fig, ax = plt.subplots(figsize=(10, 6))
        for (typology), group in plot_df.groupby(["Typology"]):
            ax.plot(group.columns[1:], group.iloc[0, 1:], marker='*', label=f"DTS-SE-AR_{rate} - AVG")

        ax.set_xlabel("AP", fontsize=20)
        ax.set_xticks([1, 2, 3, 4])
        ax.set_xticklabels(["5", "10", "15", "20"])
        if priority == "High":
            ax.set_yticks([0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30])
        else:
            ax.set_yticks([0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30])
        ax.set_ylabel("Response time (sec)", fontsize=20)
        ax.tick_params(axis='both', which='major', labelsize=20)
        ax.legend(fontsize=20)
        ax.set_xlim(ax.get_xlim())
        ax.set_ylim(ax.get_ylim())

        plt.tight_layout()
        plots_directory = os.path.join(current_directory, 'merged graph AP-AVG')
        print("Saving plot to:", plots_directory)
        os.makedirs(plots_directory, exist_ok=True)
        plt.savefig(
            os.path.join(plots_directory, f"Mean vs Arrival Rate - {priority} Priority - Arrival Rate - {rate}.png"),
            dpi=300, bbox_inches='tight')
        plt.show()
'''

dataframes = []

# Search through all folders in the current directory
for folder_name in os.listdir(current_directory):
    folder_path = os.path.join(current_directory, folder_name)
    if os.path.isdir(folder_path) and (
            folder_name.startswith("simulation result-open")):
        # Process the directory and get the combined DataFrame
        # Search for files matching the criteria within each folder
        for file_name in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file_name)
            for root, dirs, files in os.walk(file_path):

                for filename in files:
                    if filename == "boxplot_data_High_priority.csv" or filename == "boxplot_data_Low_priority.csv":
                        path = os.path.join(root, filename)
                        df = pd.read_csv(path)
                        dataframes.append(df)

# Combine all dataframes into a single dataframe
combined_df = pd.concat(dataframes, ignore_index=True)
csv_path = os.path.join(current_directory, f"combined_data_AVG_response_time.csv")
combined_df.to_csv(csv_path, index=False)

df = pd.read_csv("combined_data_AVG_response_time.csv")

# Prendi le colonne Mean e AP
mean_values = df['Mean']
ap_values = df['AP']

priority = df['Priority']

Priority = df.groupby('Priority')

pd.set_option('display.max_columns', None)  # Show all columns
pd.set_option('display.expand_frame_repr', False)  # Do not wrap rows

# Creazione di due DataFrame separati
df_high_priority = Priority.get_group('High')
#df_low_priority = Priority.get_group('Low')

#plot_data(df_low_priority , "Low")
plot_data(df_high_priority , "High")
