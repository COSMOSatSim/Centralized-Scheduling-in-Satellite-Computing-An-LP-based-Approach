import os
import pandas as pd
import matplotlib.pyplot as plt

base_dir = r'C:\Users\danil\PycharmProjects\SECMotionModel'

# Colonne da plottare (puoi aggiungere anche R Avg, etc.)
columns_to_plot = [
    'Percent Success (Low)',
    'Percent Success (High)',
    'Percent Success (Total)',
    'Percent Failed (Low)',
    'Percent Failed (High)',
    'Percent Failed (Total)',
    'R Avg'
]

old_utility_dir = [d for d in os.listdir(base_dir) if 'OldUtility' in d][0]
new_utility_dir = [d for d in os.listdir(base_dir) if 'NEWUtility' in d][0]

label_map = {
    'OldUtility': 'Base',
    'NEWUtility': 'AP-Optimal'
}

def get_data(path_label, base_subdir, target_file):
    results = []
    full_path = os.path.join(base_dir, base_subdir)

    for root, dirs, files in os.walk(full_path):
        for file in files:
            if file == target_file:
                csv_path = os.path.join(root, file)
                try:
                    df = pd.read_csv(csv_path)
                    df.columns = df.columns.str.strip()
                    for column in columns_to_plot:
                        if column in df.columns and 'AT' in df.columns and 'CPU' in df.columns:
                            for _, row in df.iterrows():
                                results.append({
                                    'label': path_label,
                                    'path': os.path.relpath(root, base_dir),
                                    'AT': row['AT'],
                                    'CPU': row['CPU'],
                                    'source_file': target_file,
                                    'column': column,
                                    'value': row[column]
                                })
                except Exception as e:
                    print(f"Errore con {csv_path}: {e}")
    return results

# Unisci i dati success e failed in un unico dataframe
data = (
    get_data('OldUtility', old_utility_dir, 'Success-stat.csv') +
    get_data('NEWUtility', new_utility_dir, 'Success-stat.csv') +
    get_data('OldUtility', old_utility_dir, 'Failed-stat.csv') +
    get_data('NEWUtility', new_utility_dir, 'Failed-stat.csv')
)

df = pd.DataFrame(data)

# Estrai tutti gli AT unici
unique_ats = sorted(df['AT'].unique())

for column in columns_to_plot:
    for source in ['Success-stat.csv', 'Failed-stat.csv']:
        print(source)
        for at in unique_ats:
            subset = df[(df['column'] == column) &
                        (df['source_file'] == source) &
                        (df['AT'] == at)]

            if subset.empty:
                continue

            plt.figure(figsize=(10, 8))

            for label in subset['label'].unique():
                for path in subset['path'].unique():
                    filtered = subset[(subset['label'] == label) & (subset['path'] == path)]
                    if not filtered.empty:
                        filtered = filtered.sort_values(by='CPU')
                        y_values = filtered['value'].values
                        x_values = filtered['CPU'].values

                        short_path = os.path.basename(path)
                        if 'DTS-simulation' in path:
                            short_path = 'DTS'
                        elif 'OrbitAware-simulation' in path:
                            short_path = 'Orbit-Aware'

                        legend_name = f"{label_map.get(label, label)} - {short_path}"
                        plt.plot(x_values, y_values, label=legend_name, marker='o')

            plt.xlabel('Service Time (sec.)', fontsize=20)
            plt.ylabel(column, fontsize=20)
            plt.xticks(sorted(subset['CPU'].unique()), fontsize=16)
            plt.yticks(fontsize=16)
            plt.legend(fontsize=16)
            plt.grid(axis='y', linestyle='--', alpha=0.5)
            plt.tight_layout()

            # Nome file pulito
            output_type = 'Failed' if 'Failed' in source else 'Success'
            safe_column = column.replace(' ', '_').replace('(', '').replace(')', '')
            filename = f"{safe_column}_by_AT_{at}_{output_type}.png"
            output_path = os.path.join(base_dir, filename)

            print(output_path)
            plt.savefig(output_path)
            plt.show()

# ===================== BARPLOT SEPARATI PER R 90% E R 95% =====================

percentile_columns = ['R 90%', 'R 95%']
df_barplot = []

for label in ['OldUtility', 'NEWUtility']:
    for root, dirs, files in os.walk(os.path.join(base_dir, old_utility_dir if label == 'OldUtility' else new_utility_dir)):
        for file in files:
            if file == 'Success-stat.csv':
                path = os.path.join(root, file)
                try:
                    df = pd.read_csv(path)
                    df.columns = df.columns.str.strip()
                    if all(col in df.columns for col in ['AT', 'CPU'] + percentile_columns):
                        for _, row in df.iterrows():
                            df_barplot.append({
                                'AT': row['AT'],
                                'CPU': row['CPU'],
                                'Simulation': 'DTS' if 'DTS-simulation' in root else 'Orbit',
                                'label': label,
                                'R 90%': row['R 90%'],
                                'R 95%': row['R 95%']
                            })
                except Exception as e:
                    print(f"Errore durante la lettura per barplot: {e}")

df_barplot = pd.DataFrame(df_barplot)

# Funzione per creare i barplot per ciascun percentile
def plot_percentile_bar(df, percentile_col, output_prefix):
    bar_w = 0.12
    for at in sorted(df['AT'].unique()):
        plt.figure(figsize=(10, 8))
        df_at = df[df['AT'] == at]
        cpus = sorted(df_at['CPU'].unique())

        for idx, sim in enumerate(['DTS', 'Orbit']):
            for lid, label in enumerate(['OldUtility', 'NEWUtility']):
                sub = df_at[(df_at['Simulation'] == sim) & (df_at['label'] == label)].set_index('CPU').reindex(cpus)
                offset = (idx * 2 + lid) * bar_w * 1.5
                plt.bar([i + offset for i in range(len(cpus))],
                        sub[percentile_col], width=bar_w,
                        label=f"{label_map[label]} - {'DTS-TMAX' if sim == 'DTS' else 'OrbitAware'}")

        plt.xlabel('Service Time (sec.)', fontsize=20)
        plt.ylabel(f'Response Time {percentile_col}', fontsize=20)
        tick_pos = [i + 1.5 * bar_w for i in range(len(cpus))]
        plt.xticks(tick_pos, cpus, fontsize=20)
        plt.yticks(fontsize=20)
        plt.ylim(0, 105)
        plt.grid(axis='y', linestyle='--', alpha=0.5)
        plt.legend(fontsize=15)
        plt.tight_layout()

        filename = f"{output_prefix}_{percentile_col.replace(' ', '').replace('%','p')}_AT_{at}.png"
        plt.savefig(os.path.join(base_dir, filename), dpi=300)
        print(f"Saved barplot: {filename}")
        plt.close()

# Crea i due barplot separati
plot_percentile_bar(df_barplot, 'R 90%', 'GroupedBar')
plot_percentile_bar(df_barplot, 'R 95%', 'GroupedBar')
