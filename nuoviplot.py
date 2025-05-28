import os
import pandas as pd
import matplotlib.pyplot as plt

# ---- File paths (update as needed) ----
orbit_failed_file = r'C:\Users\danil\PycharmProjects\SECMotionModel\OrbitAware-simulation result-System_AP5\simulation result_seed_42\Failed-stat.csv'
dts_failed_file   = r'C:\Users\danil\PycharmProjects\SECMotionModel\DTS-simulation result-System_AP5\simulation result_seed_42\Failed-stat.csv'
orbit_success_file= r'C:\Users\danil\PycharmProjects\SECMotionModel\OrbitAware-simulation result-System_AP5\simulation result_seed_42\Success-stat.csv'
dts_success_file  = r'C:\Users\danil\PycharmProjects\SECMotionModel\DTS-simulation result-System_AP5\simulation result_seed_42\Success-stat.csv'

# Output directory for plots
output_dir = os.path.join(os.getcwd(), 'stat_plots_NEWUtility_OrbitBestRandomServer_DTSWorstRandomServer_DTS-AP-NonOptimal')
os.makedirs(output_dir, exist_ok=True)

# Read failed stats
df_orbit_failed = pd.read_csv(orbit_failed_file)
df_dts_failed   = pd.read_csv(dts_failed_file)
df_orbit_failed['Simulation'] = 'Orbit'
df_dts_failed['Simulation']   = 'DTS'
_df_fail = pd.concat([df_orbit_failed, df_dts_failed], ignore_index=True)

# Read success stats
df_orbit_succ = pd.read_csv(orbit_success_file)
df_dts_succ   = pd.read_csv(dts_success_file)
df_orbit_succ['Simulation'] = 'Orbit'
df_dts_succ['Simulation']   = 'DTS'
_df_succ = pd.concat([df_orbit_succ, df_dts_succ], ignore_index=True)

# 1) Stacked area & Line: Success (Total, High, Low)

def plot_stacked_by_priority_and_simulation(df, at_column, metric_cols, value_labels, ylabel_base, plot_type, output_dir):
    """
    Crea stacked plot per ogni AT e simulazione (DTS / Orbit), con breakdown High e Low.

    Args:
        df: DataFrame contenente i dati.
        at_column: nome della colonna AT.
        metric_cols: lista di tuple [(col_high, label_high), (col_low, label_low)].
        value_labels: lista delle etichette da usare nello stack plot (es. ['High Priority', 'Low Priority']).
        ylabel_base: prefisso della label per asse Y (es. 'Success Rate (%)').
        plot_type: tipo di metrica ('success' o 'failed'), usato nel nome del file.
        output_dir: path alla directory di output per i plot.
    """
    ats = df[at_column].unique()

    for at in ats:
        df_at = df[df[at_column] == at]

        for sim in ['DTS', 'Orbit']:
            df_sim = df_at[df_at['Simulation'] == sim]

            # Aggrega valori high e low
            data = {}
            x = None
            for col, label in metric_cols:
                df_agg = df_sim.groupby('CPU')[col].mean().reset_index().sort_values('CPU')
                data[label] = df_agg[col].values
                if x is None:
                    x = df_agg['CPU'].values

            # Plot
            plt.figure(figsize=(10, 8))
            plt.stackplot(
                x,
                data[metric_cols[0][1]],  # High
                data[metric_cols[1][1]],  # Low
                labels=value_labels,
                alpha=0.6
            )
            plt.xlabel('Service Time (sec.)', fontsize=20)
            plt.ylabel(ylabel_base, fontsize=20)
            plt.xticks(x, fontsize=20)
            plt.yticks(fontsize=20)

            plt.ylim(0, 101)
            plt.grid(axis='y', linestyle='--', alpha=0.6)
            plt.legend(fontsize=20)
            plt.tight_layout()
            filename = f'stacked_{plot_type}_{sim}_{at}.png'.replace(" ", "_").lower()
            plt.savefig(os.path.join(output_dir, filename), dpi=300)
            plt.close()

success_cols = [
    ('Percent Success (High)', 'High Success'),
    ('Percent Success (Low)', 'Low Success')
]
# Definizione colonne per i fallimenti
failure_cols = [
    ('Percent Failed (High)', 'High Failed'),
    ('Percent Failed (Low)', 'Low Failed')
]

plot_stacked_by_priority_and_simulation(
    df=_df_succ,
    at_column='AT',
    metric_cols=success_cols,
    value_labels=['High Priority', 'Low Priority'],
    ylabel_base='Success Rate (%)',
    plot_type='success',
    output_dir=output_dir
)


# Chiamata alla funzione
plot_stacked_by_priority_and_simulation(
    df=_df_fail,
    at_column='AT',
    metric_cols=failure_cols,
    value_labels=['High Priority', 'Low Priority'],
    ylabel_base='Failure Rate (%)',
    plot_type='failed',
    output_dir=output_dir
)


##Stacker per ogni AT Success
for col, ylabel in success_cols:
    for at in sorted(_df_succ['AT'].unique()):
        # filter by AT and aggregate
        df_at = _df_succ[_df_succ['AT'] == at]
        df_agg = df_at.groupby(['CPU','Simulation'])[col].mean().reset_index()
        pivot = df_agg.pivot(index='CPU', columns='Simulation', values=col).sort_index()
        x = pivot.index


# 2) Stacked area & Line: Failed (Total, High, Low)

def plot_stacked_and_line_per_AT(
    df: pd.DataFrame,
    metric_cols: list[tuple[str,str]],
    df_label: str,
    output_dir: str,
    ylims: dict[str, tuple[float,float]] = None
):
    """
    Per ogni (col, label) in metric_cols:
      1) genera un stacked area plot su tutte le CPU (indipendentemente da AT)
      2) genera un line plot separato per ogni AT

    df           : DataFrame contenente colonne ['CPU','Simulation','AT', col]
    metric_cols  : lista di tuple (nome_colonna, descrizione per ylabel)
    df_label     : prefisso per label di legenda ('Failed' o 'Success')
    output_dir   : cartella di destinazione dei PNG
    ylims        : dizionario opzionale { 'High': (min,max), 'Low':..., 'Total':... }
    """
    sims = ['DTS', 'Orbit']
    labels_map = { 'DTS': 'DTS-TMAX', 'Orbit': 'OrbitAware' }

    for col, descr in metric_cols:
        # 1) Stacked area su tutte le CPU
        df_agg = df.groupby(['CPU','Simulation'])[col].mean().reset_index()
        pivot = df_agg.pivot(index='CPU',columns='Simulation',values=col).sort_index()


        # 2) Line plot per ogni AT
        for at_value in sorted(df['AT'].unique()):
            df_at = df[df['AT'] == at_value]
            df_agg_at = df_at.groupby(['CPU','Simulation'])[col].mean().reset_index()
            pivot_at = df_agg_at.pivot(index='CPU',columns='Simulation',values=col).sort_index()
            x_at = pivot_at.index

            plt.figure(figsize=(10,8))
            for sim in sims:
                if sim in pivot_at.columns:
                    plt.plot(
                        x_at, pivot_at[sim],
                        marker='o', linestyle='-',
                        label=labels_map[sim]
                    )
            plt.xlabel('Service Time (sec.)', fontsize=20)
            plt.ylabel(descr, fontsize=20)
            plt.xticks(x_at, fontsize=20)
            plt.yticks(fontsize=20)

            # auto y-limits per High/Low/Total se forniti
            lim_key = 'High' if 'High' in descr else ('Low' if 'Low' in descr else 'Total')
            if ylims and lim_key in ylims:
                plt.ylim(*ylims[lim_key])
            else:
                plt.ylim(0,101)
            plt.grid(axis='y', linestyle='--', alpha=0.6)
            plt.legend(fontsize=20)
            plt.tight_layout()
            filename = f'line_{col.replace(" ","_").replace("%","pct")}_AT{str(at_value).replace(".","_")}.png'
            plt.savefig(os.path.join(output_dir, filename), dpi=300)
            plt.close()

# ---------------------------------------------------------

# Success
success_cols = [
    ('Percent Success (Total)', 'Success Total (%)'),
    ('Percent Success (High)',  'Success High Priority (%)'),
    ('Percent Success (Low)',   'Success Low Priority (%)')
]
plot_stacked_and_line_per_AT(
    df=_df_succ,
    metric_cols=success_cols,
    df_label='Success',
    output_dir=output_dir,
    ylims={'High':(0,101), 'Low':(0,101)}
)

# Failed (con limiti personalizzati se vuoi)
failure_cols = [
    ('Percent Failed (Total)', 'Failed Total (%)'),
    ('Percent Failed (High)',  'Failed High Priority (%)'),
    ('Percent Failed (Low)',   'Failed Low Priority (%)')
]
plot_stacked_and_line_per_AT(
    df=_df_fail,
    metric_cols=failure_cols,
    df_label='Failed',
    output_dir=output_dir,
    ylims={ 'High':(0,101), 'Low':(0,101)}
)



# 3) Line plots: Average Response Time per AT
for at in sorted(_df_succ['AT'].unique()):
    df_at = _df_succ[_df_succ['AT']==at]
    x = sorted(df_at['CPU'].unique())
    plt.figure(figsize=(10,8))
    for sim in ['DTS','Orbit']:
        sub = df_at[df_at['Simulation']==sim].set_index('CPU').loc[x]
        if sim == 'DTS':
            plt.plot(x, sub['R Avg'], marker='o', linestyle='-', label='DTS-TMAX')
        else: plt.plot(x, sub['R Avg'], marker='o', linestyle='-', label='OrbitAware')
    plt.xlabel('Service Time (sec.)', fontsize=20)
    plt.ylabel('Avg Response Time (sec)', fontsize=20)
    #plt.title(f'Avg Response Time – AT={at}')
    plt.xticks(x, fontsize=20)
    plt.yticks(fontsize=20)

    plt.ylim(0,101)
    plt.grid(axis='y', linestyle='--', alpha=0.6)
    plt.legend(fontsize=20)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir,f'avg_response_at_{str(at).replace(".","_")}.png'),dpi=300)
    plt.close()

# 4) Line plots: R 90% per AT
for at in sorted(_df_succ['AT'].unique()):
    df_at = _df_succ[_df_succ['AT']==at]
    x = sorted(df_at['CPU'].unique())
    plt.figure(figsize=(10,8))
    for sim in ['DTS','Orbit']:
        sub = df_at[df_at['Simulation']==sim].set_index('CPU').loc[x]
        plt.plot(x, sub['R 90%'], marker='o', linestyle='-', label=f"{'DTS-TMAX' if sim == 'DTS' else 'OrbitAware'} ")
    plt.xlabel('Service Time (sec.)', fontsize=20)
    plt.ylabel('$\mathrm{Response\ Time\ 90^{\mathrm{th}}\  Percentile\ (sec)}$', fontsize=20)
    #plt.title(f'90th Percentile – AT={at}')
    plt.xticks(x, fontsize=20)
    plt.yticks(fontsize=20)

    plt.ylim(0,101)
    plt.grid(axis='y', linestyle='--', alpha=0.6)
    plt.legend(fontsize=20)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir,f'r90_at_{str(at).replace(".","_")}.png'),dpi=300)
    plt.close()

# 5) Line plots: R 95% per AT
for at in sorted(_df_succ['AT'].unique()):
    df_at = _df_succ[_df_succ['AT']==at]
    x = sorted(df_at['CPU'].unique())
    plt.figure(figsize=(10,8))
    for sim in ['DTS','Orbit']:
        sub = df_at[df_at['Simulation']==sim].set_index('CPU').loc[x]
        plt.plot(x, sub['R 95%'], marker='o', linestyle='-', label=f"{'DTS-TMAX' if sim == 'DTS' else 'OrbitAware'} ")
    plt.xlabel('Service Time (sec.)', fontsize=20)
    plt.ylabel('$\mathrm{Response\ Time\ 95^{\mathrm{th}}\  Percentile\ (sec)}$', fontsize=20)
    #plt.title(f'95th Percentile – AT={at}')
    plt.xticks(x, fontsize=20)
    plt.yticks(fontsize=20)

    plt.ylim(0,101)
    plt.grid(axis='y', linestyle='--', alpha=0.6)
    plt.legend(fontsize=20)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir,f'r95_at_{str(at).replace(".","_")}.png'),dpi=300)
    plt.close()

# 6) Grouped bar: R 90% and R 95%
df_pct = _df_succ.groupby(['CPU','Simulation'])[['R 90%','R 95%']].mean().reset_index()
cpus = sorted(df_pct['CPU'].unique())
bar_w = 0.1
inner_gap = 0.1
for at in sorted(_df_succ['AT'].unique()):
    plt.figure(figsize=(10,8))
    df_at = _df_succ[_df_succ['AT']==at]
    x = sorted(df_at['CPU'].unique())

    for idx,sim in enumerate(['DTS','Orbit']):
        sub = df_at[df_at['Simulation'] == sim].set_index('CPU').loc[x]
        offs = idx*(2*bar_w)
        plt.bar([i+offs for i in range(len(cpus))], sub['R 90%'], width=bar_w, label = f"{'DTS-TMAX' if sim == 'DTS' else 'OrbitAware'} 90%")
        plt.bar([i+offs+bar_w for i in range(len(cpus))], sub['R 95%'], width=bar_w, label = f"{'DTS-TMAX' if sim == 'DTS' else 'OrbitAware'} 95%")
    plt.xlabel('Service Time (sec.)', fontsize=20)
    plt.ylabel('Response Time Percentile (sec)', fontsize=20)
    ticks = [i+bar_w*1.5 for i in range(len(cpus))]
    plt.xticks(ticks, cpus, fontsize=20)
    plt.yticks(fontsize=20)

    plt.ylim(0,101)
    plt.grid(axis='y', linestyle='--', alpha=0.6)
    plt.legend(fontsize=20)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir,f'grouped_r90_r95_at_{at}.png'),dpi=300)
    plt.close()

# 7) Line plots: Percent Exec After Sunset Total per AT
for at in sorted(_df_fail['AT'].unique()):
    df_at = _df_fail[_df_fail['AT']==at]
    x = sorted(df_at['CPU'].unique())
    plt.figure(figsize=(10,8))
    for sim in ['DTS','Orbit']:
        sub = df_at[df_at['Simulation']==sim].set_index('CPU').loc[x]
        plt.plot(x, sub['Percent Exec After Sunset Total'], marker='o', linestyle='-', label=f"{'DTS-TMAX' if sim == 'DTS' else 'OrbitAware'} ")
    plt.xlabel('Service Time (sec.)', fontsize=20)
    plt.ylabel('Executed After Sunset (%)', fontsize=20)
    #plt.title(f'Exec After Sunset – AT={at}')
    plt.xticks(x, fontsize=20)
    plt.yticks(fontsize=20)

    plt.ylim(0,101)
    plt.grid(axis='y', linestyle='--', alpha=0.6)
    plt.legend(fontsize=20)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir,f'exec_after_sunset_at_{str(at).replace(".","_")}.png'),dpi=300)
    plt.show()
    plt.close()
