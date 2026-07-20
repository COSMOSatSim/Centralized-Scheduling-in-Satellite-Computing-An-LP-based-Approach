import pandas as pd

# Carica il tuo dataframe CSV
df = pd.read_csv('results_esp_7/summary_statistics.csv')

# Definisci le metriche su cui calcolare la media (Time/Energy/Dijkstra vengono accorpati)
metrics = ['Success_Rate_PCT', 'Avg_Total_Response_ms', 'Avg_System_Exec_ms', 'Rej_Deadline_PCT', 'Rej_Insuff_CPU_PCT']

# Raggruppa per i livelli richiesti e calcola la media
df_agg = df.groupby(['Deadline', 'Batch_Size', 'Batch_Timeout', 'Arrival_Rate_ReqSec'])[metrics].mean().reset_index()

# Stampa l'output LaTeX riga per riga
for dl in df_agg['Deadline'].unique():
    df_dl = df_agg[df_agg['Deadline'] == dl]
    dl_rows = len(df_dl)
    first_dl = True
    
    for bs in df_dl['Batch_Size'].unique():
        df_bs = df_dl[df_dl['Batch_Size'] == bs]
        for bt in df_bs['Batch_Timeout'].unique():
            df_bt = df_bs[df_bs['Batch_Timeout'] == bt]
            bt_rows = len(df_bt)
            first_bt = True
            
            for idx, row in df_bt.iterrows():
                # Gestione del multirow per evitare ripetizioni
                dl_str = f"\\multirow{{{dl_rows}}}{{*}}{{{int(row['Deadline'])}}}" if first_dl else ""
                bs_str = f"\\multirow{{{bt_rows}}}{{*}}{{{int(row['Batch_Size'])}}}" if first_bt else ""
                bt_str = f"\\multirow{{{bt_rows}}}{{*}}{{{float(row['Batch_Timeout'])}}}" if first_bt else ""
                
                print(f"        {dl_str} & {bs_str} & {bt_str} & {int(row['Arrival_Rate_ReqSec'])} & "
                      f"{row['Success_Rate_PCT']:.2f} & {row['Avg_Total_Response_ms']:.3f} & "
                      f"{row['Avg_System_Exec_ms']:.3f} & {row['Rej_Deadline_PCT']:.2f} & "
                      f"{row['Rej_Insuff_CPU_PCT']:.2f} \\\\")
                
                first_dl = False
                first_bt = False
            print(r"        \addlinespace")
    print(r"        \midrule")