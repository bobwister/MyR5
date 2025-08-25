import streamlit as st
import pandas as pd
import asyncio
from main import get_renault_data  # import de la fonction async
from main import format_date
import pytz

def get_secret_creds():
    """Retourne {'email':..., 'password':...} si présents dans st.secrets, sinon None."""
    try:
        section = st.secrets.get("myrenault", None)
        if not section:
            return None
        email = section.get("email")
        password = section.get("password")
        if email and password:
            return {"email": email, "password": password}
    except Exception:
        pass
    return None

st.set_page_config(
    page_title="Renault Dashboard",
    page_icon="https://www.blogauto.com.br/wp-content/2024/02/Renault-5-e-Tech-10.jpg",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(
    """
    <h1 style='display: flex; align-items: center; gap: 10px;'>
        <img src="https://www.blogauto.com.br/wp-content/2024/02/Renault-5-e-Tech-10.jpg"
             width="80"
             style="border-radius: 8px;">
        Données Renault R5 E-Tech
    </h1>
    """,
    unsafe_allow_html=True
)

# === Initialisation de session_state pour stocker les données ===
if "attrs" not in st.session_state:
    st.session_state.attrs = None
if "email" not in st.session_state:
    st.session_state.email = ""
if "password" not in st.session_state:
    st.session_state.password = ""

# -------------------------------------------------------------------------
# Sidebar : secrets si présents, sinon formulaire
# -------------------------------------------------------------------------
st.sidebar.header("🔑 Connexion MyRenault")

secret_creds = get_secret_creds()

if secret_creds:
    # Secrets présents : on n'affiche PAS le formulaire, juste un bouton
    st.sidebar.info("Identifiants chargés depuis secrets.toml")
    submit = True # st.sidebar.button("✅ Se connecter / Rafraîchir", use_container_width=True)
    email = secret_creds["email"]
    password = secret_creds["password"]
else:
    # Pas de secrets → formulaire classique
    with st.sidebar.form("login_form", clear_on_submit=False):
        email = st.text_input("Email MyRenault", value=st.session_state.email)
        password = st.text_input("Mot de passe", type="password", value=st.session_state.password)
        submit = st.form_submit_button("✅ Se connecter / Rafraîchir")

# === Fonction de refresh ===
def refresh_data(email, password):
    if email and password:
        with st.spinner("Chargement des données Renault..."):
            # get_renault_data doit être défini/importé dans ton code
            st.session_state.attrs = asyncio.run(get_renault_data(email, password))
            # Mémoriser (retire la ligne du password si tu préfères ne pas stocker)
            st.session_state.email = email
            st.session_state.password = password
    else:
        st.warning("Merci de renseigner vos identifiants.")

# === Exécution quand on valide ===
if submit:
    refresh_data(email, password)

# === Utilisation des données ===
attrs = st.session_state.attrs
if attrs:
    # st.write("🚗 Données Renault :", attrs)

    # === Bouton de refresh ===
    st.write("Dernière mise à jour :", attrs['last_update'])
    # st.button("🔄 Rafraîchir les données", on_click=refresh_data)

    # --- Création des onglets ---
    tab_info, tab_charge, tab_map = st.tabs(["Infos", "Recharges", "Carte"])

    # --- Batterie ---
    with tab_info:
        st.subheader("🔋 État de la batterie")
        usable_capacity = attrs['usable_capacity']
        st.write("Niveau actuel", f"{attrs['battery_level']} % ({attrs['battery_level'] * usable_capacity / 100:.2f} kWh / {int(usable_capacity)} kWh)")

        # --- Statistiques globales ---
        st.subheader("⚡ Statistiques globales")
        charge_stats = attrs['charge_stats']
        st.write(f"Énergie totale rechargée : {charge_stats['total_energy_charged']} kWh (en {charge_stats['nb_charges']} recharges)")
        st.write(f"Kilométrage parcouru : {attrs['kilometrage']} km")
        st.write(f"Consommation moyenne : {charge_stats['avg_consumption']} kWh/100km")
        st.write(f"Autonomie restante officielle : {attrs['battery_autonomy']} km / {attrs['battery_max_autonomy']} km")
        #st.write(f"Autonomie max officielle (100% charge) : {attrs['battery_max_autonomy']} km")
        st.write(f"Autonomie restante recalculée avec conso moyenne : {attrs['battery_autonomy_estimation']} km / {attrs['battery_max_autonomy_real']} km")
        #st.write(f"Autonomie max recalculée (100% charge) avec conso moyenne : {attrs['battery_max_autonomy_real']} km")
        
        # Branchée ?
        if attrs['plugStatus'] == 1:
            st.write("🔌 Branchée")
        else:
            st.write("❌ Débranchée")

        # En charge ?
        if attrs['chargingStatus'] == 0.0:
            st.write("⏸️ Pas en charge")
        elif attrs['chargingStatus'] == 0.1:
            st.write("🕒 Charge planifiée")
        elif attrs['chargingStatus'] == 1.0:#0.2
            st.write("⚡ En charge")

    with tab_charge:

        # --- Historique des recharges ---
        st.subheader("⚡ Historique des recharges")
        charges_df = pd.DataFrame(attrs['charge_history'])

        # Ajout d'une colonne "marqueur" avec une icône si la charge est manuelle
        charges_df["🔖"] = charges_df["fakeCharge"].apply(lambda x: "✨" if x else "")

        # Tri des lignes
        charges_df.sort_values('chargeStartDate', ascending=False, inplace=True)

        # Afficher le tableau des charges
        if not charges_df.empty:
            # Convetir les dates UTC en datetime
            charges_df['chargeStartDate'] = pd.to_datetime(charges_df['chargeStartDate'], utc=True)
            charges_df['chargeEndDate'] = pd.to_datetime(charges_df['chargeEndDate'], utc=True)

            # Fuseau horaire local (ex: Paris)
            paris_tz = pytz.timezone('Europe/Paris')

            # Convertir en heure locale
            charges_df['chargeStartDateLocal'] = charges_df['chargeStartDate'].dt.tz_convert(paris_tz)
            charges_df['chargeEndDateLocal'] = charges_df['chargeEndDate'].dt.tz_convert(paris_tz)

            # Formater les dates en DD/MM/YYYY HH:MM:SS
            charges_df['chargeStartDateFormatted'] = charges_df['chargeStartDateLocal'].dt.strftime('%d/%m/%Y à %H:%M:%S')
            charges_df['chargeEndDateFormatted'] = charges_df['chargeEndDateLocal'].dt.strftime('%d/%m/%Y à %H:%M:%S')

            # Ajouter le symbole % pour le niveau de batterie
            charges_df['chargeStartBatteryLevelStr'] = charges_df['chargeStartBatteryLevel'].astype(str) + " %"
            charges_df['chargeEndBatteryLevelStr'] = charges_df['chargeEndBatteryLevel'].astype(str) + " %"
            charges_df['chargePercentRecoveredStr'] = charges_df['chargePercentRecovered'].round(2).astype(str) + " %"

            # Ajouter l'unité kWh pour la quantité d'énergie rechargée
            charges_df['chargeEnergyRecoveredStr'] = charges_df['chargeEnergyRecovered'].round(2).astype(str) + " kWh"

            # Conversion de la durée de recharge en heures et ajouter l'unité de temps
            charges_df['chargeDurationStr'] = (charges_df['chargeDuration'] / 60).round(2).astype(str) + " h"

            # Conversion de l'unité kW de puissance de recharge
            charges_df['chargePowerStr'] = charges_df['chargePower'].round(2).astype(str) + " kW"

            # Pour le tableau Streamlit, on peut afficher les colonnes formatées
            display_df = charges_df[[
                'chargeStartDateFormatted',
                'chargeEndDateFormatted',
                'chargeStartBatteryLevelStr',
                'chargeEndBatteryLevelStr',
                'chargeEnergyRecoveredStr',
                'chargePercentRecoveredStr',
                'chargeDurationStr',
                'chargePowerStr',
            ]].rename(columns={
                'chargeStartDateFormatted': 'Début charge',
                'chargeEndDateFormatted': 'Fin charge',
                'chargeStartBatteryLevelStr': 'Niveau batterie début',
                'chargeEndBatteryLevelStr': 'Niveau batterie fin',
                'chargeEnergyRecoveredStr': 'Énergie rechargée (kWh)',
                'chargePercentRecoveredStr': 'Pourcentage récupéré',
                'chargeDurationStr': 'Durée de charge (h)',
                'chargePowerStr': 'Puissance de charge (kW)'
            })

            # Calcul des totaux pour les colonnes numériques
            total_energy = display_df['Énergie rechargée (kWh)'].str.replace(' kWh','').astype(float).sum()
            total_percent = display_df['Pourcentage récupéré'].str.replace(' %','').astype(float).sum()
            total_duration = display_df['Durée de charge (h)'].str.replace(' h','').astype(float).sum()
            total_power = total_energy / total_duration

            # Créer la ligne TOTAL avec le même format que display_df
            total_row = {
                'Début charge': '<b>TOTAL</b>',
                'Fin charge': '',
                'Niveau batterie début': '',
                'Niveau batterie fin': '',
                'Énergie rechargée (kWh)': f'{total_energy:.2f} kWh',
                'Pourcentage récupéré': f'{total_percent:.2f} %',
                'Durée de charge (h)': f'{total_duration:.2f} h',
                'Puissance de charge (kW)': f'{total_power:.2f} kW'
            }
            
            # Insérer la ligne TOTAL au début
            display_df_total = pd.concat([pd.DataFrame([total_row]), display_df], ignore_index=True)

            # Nombre de lignes de données (hors TOTAL)
            n = len(display_df)

            # Générer numérotation décroissante pour les lignes de données
            index_labels = ['TOTAL']  # première ligne = TOTAL
            for i, idx in enumerate(charges_df.index):
                num = n - i
                if charges_df.loc[idx, "fakeCharge"]:
                    label = f"{num} <span title=\"Ajout magique d'une charge manquante dans l'API\">✨</span>"
                else:
                    label = f"{num}"
                index_labels.append(label)

            display_df_total.index = index_labels

            # Mettre en gras les valeurs de la première ligne (TOTAL)
            display_df_total.iloc[0] = display_df_total.iloc[0].apply(lambda x: f"<b>{x}</b>")

            # Afficher le tableau avec HTML pour les icônes et index personnalisé
            st.write(display_df_total.to_html(escape=False), unsafe_allow_html=True)

            # Afficher le graphique de l'évolution du niveau de batterie
            #st.line_chart(charges_df.set_index('chargeStartDate')['chargeEndBatteryLevel'])

            # Reconstruire les points pour la courbe
            battery_times = []
            battery_levels = []

            for _, row in charges_df.iterrows():
                # Début de charge
                battery_times.append(row['chargeStartDate'])
                battery_levels.append(row['chargeStartBatteryLevel'])
                # Fin de charge
                battery_times.append(row['chargeEndDate'])
                battery_levels.append(row['chargeEndBatteryLevel'])

            df_plot = pd.DataFrame({
                'time': battery_times,
                'level': battery_levels
            })

            # Indexer sur le temps
            df_plot.set_index('time', inplace=True)

            # Affichage de la courbe
            st.subheader("Évolution du niveau de batterie")
            st.line_chart(df_plot['level'])

    with tab_map:
        # --- Carte GPS ---
        st.subheader("🗺️ Localisation du véhicule")
        df = pd.DataFrame(
            [[attrs['gps']['latitude'], attrs['gps']['longitude']]],
            columns=["lat", "lon"]
        )
        st.map(df, zoom=12)