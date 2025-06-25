import os
import pandas as pd
import matplotlib.pyplot as plt

# 1) Configurazione
base_dir = r'C:\Users\danil\PycharmProjects\SECMotionModel'

folders = {
    'DTS-AP optimal':       'DTS-AP optimal-sim_SystemAP5',
    'DTS-base':             'DTS-base-sim_SystemAP5',
    'OrbitAware + Utility': 'OrbitAware Utility-sim_SystemAP5',
    'OrbitAware':           'OrbitAware-sim_SystemAP5'
}

# Dove mettere tutti i plot
output_dir = os.path.join(base_dir, 'barplots_percentili')
os.makedirs(output_dir, exist_ok=True)

# Colonne da estrarre
columns_to_plot = [
    'Percent Success (Low)',
    'Percent Success (High)',
    'Percent Success (Total)',
    'Percent Failed (Low)',
    'Percent Failed (High)',
    'Percent Failed (Total)',
    'R Avg'
]

# Funzione per leggere CSV
def get_data(label, folder, source_file):
    results = []
    folder_path = os.path.join(base_dir, folder)

    for root, dirs, files in os.walk(folder_path):
        if source_file in files:
            path = os.path.join(root, source_file)
            try:
                df = pd.read_csv(path)
                df.columns = df.columns.str.strip()
                # estrai solo se ha AT, CPU e almeno una delle colonne_to_plot
                if 'AT' in df.columns and 'CPU' in df.columns:
                    for col in columns_to_plot:
                        if col in df.columns:
                            for _, row in df.iterrows():
                                results.append({
                                    'label': label,
                                    'AT': row['AT'],
                                    'CPU': row['CPU'],
                                    'source_file': source_file,
                                    'column': col,
                                    'value': row[col]
                                })
            except Exception as e:
                print(f"Errore leggendo {path}: {e}")
    return results

# 2) Costruiamo il DataFrame unico
data = []
for label, folder in folders.items():
    data += get_data(label, folder, 'Success-stat.csv')
    data += get_data(label, folder, 'Failed-stat.csv')

df = pd.DataFrame(data)

# Verifica rapida
if 'AT' not in df.columns:
    raise RuntimeError("AT non trovata: controlla che i CSV esistano ed abbiano la colonna AT")

unique_ats = sorted(df['AT'].unique())

# 3) Plot line per ogni colonna/AT/source
for column in columns_to_plot:
    for source in ['Success-stat.csv','Failed-stat.csv']:
        for at in unique_ats:
            subset = df[(df['column']==column)&(df['source_file']==source)&(df['AT']==at)]
            if subset.empty:
                continue

            plt.figure(figsize=(10,6))
            for lbl in subset['label'].unique():
                sub2 = subset[subset['label']==lbl].sort_values('CPU')
                plt.plot(sub2['CPU'], sub2['value'], marker='o', label=lbl)

            plt.title(f"{column}  ({source.replace('.csv','')}) – AT={at}")
            plt.xlabel('CPU')
            plt.ylabel(column)
            plt.xticks(sorted(subset['CPU'].unique()))
            plt.grid(axis='y', linestyle='--', alpha=0.5)
            plt.legend()
            plt.tight_layout()

            safe_col = column.replace(' ','_').replace('(','').replace(')','')
            typ = 'Success' if 'Success' in source else 'Failed'
            fname = f"{safe_col}_AT{at}_{typ}.png"
            plt.savefig(os.path.join(output_dir, fname), dpi=300)
            plt.close()

# 4) Barplot separati per R 90% e R 95%
percentile_cols = ['R 90%','R 95%']
df_bar = []

for label, folder in folders.items():
    folder_path = os.path.join(base_dir, folder)
    for root, dirs, files in os.walk(folder_path):
        if 'Success-stat.csv' in files:
            path = os.path.join(root, 'Success-stat.csv')
            df2 = pd.read_csv(path)
            df2.columns = df2.columns.str.strip()
            if all(c in df2.columns for c in ['AT','CPU']+percentile_cols):
                for _, row in df2.iterrows():
                    df_bar.append({
                        'label': label,
                        'AT': row['AT'],
                        'CPU': row['CPU'],
                        'R 90%': row['R 90%'],
                        'R 95%': row['R 95%']
                    })

df_bar = pd.DataFrame(df_bar)

def plot_bar(dfb, col):
    bar_w = 0.2
    for at in sorted(dfb['AT'].unique()):
        sub = dfb[dfb['AT']==at]
        cpus = sorted(sub['CPU'].unique())
        plt.figure(figsize=(10,6))
        for i, lbl in enumerate(sorted(sub['label'].unique())):
            s2 = sub[sub['label']==lbl].set_index('CPU').reindex(cpus)
            offs = i*bar_w
            plt.bar([x+offs for x in range(len(cpus))], s2[col], width=bar_w, label=lbl)
        plt.xlabel('CPU'); plt.ylabel(col)
        ticks = [i+bar_w*(len(sub['label'].unique())-1)/2 for i in range(len(cpus))]
        plt.xticks(ticks, cpus)
        plt.title(f"{col} – AT={at}")
        plt.legend(); plt.tight_layout()
        fname = f"Bar_{col.replace(' ','_').replace('%','p')}_AT{at}.png"
        plt.savefig(os.path.join(output_dir, fname), dpi=300)
        plt.close()

plot_bar(df_bar, 'R 90%')
plot_bar(df_bar, 'R 95%')
