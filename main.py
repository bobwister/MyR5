import aiohttp
import asyncio
from renault_api.renault_client import RenaultClient
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

USABLE_CAPACITY = 52.0 # capacité utile de la batterie
DEFAULT_CHARGE_DURATION = 359 # durée de recharge utilisé lorsqu'une charge a été oubliée par l'API et qu'on l'ajoute de manière automatique et forcée

def format_date(date_str: str) -> str:
    # on transforme la date ISO en datetime
    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))

    # conversion de l'heure UTC au fuseau horaire de Paris
    dt = dt.astimezone(ZoneInfo("Europe/Paris"))
    
    # noms des jours
    jours = ["Lun.", "Mar.", "Mer.", "Jeu.", "Ven.", "Sam.", "Dim."]
    jour_sem = jours[dt.weekday()]  # lundi = 0

    # ajout des secondes avec %S
    return f"{jour_sem} {dt.strftime('%d/%m à %Hh%M:%S')}"

def shift_date(date_str: str, days: int = -1) -> str:
    """
    Décale une date ISO8601 (UTC) de 'days' jours.
    Exemple de date attendue : '2025-08-06T12:24:06Z'
    """
    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    shifted = dt + timedelta(days=days)
    return shifted.strftime("%Y-%m-%dT%H:%M:%SZ")

async def get_renault_data(email, password):
    async with aiohttp.ClientSession() as websession:
        
        client = RenaultClient(websession=websession, locale="fr_FR")

        # Connecttion avec les identifiants MyRenault
        await client.session.login(email, password)

        # Liste des comptes liés
        persons = await client.get_person()

        # Récupération de mon account (type MYRENAULT)
        my_account = None

        for acc in persons.accounts:
            if acc.accountType == "MYRENAULT":
                my_account = acc
                break  # on prend le premier trouvé, généralement il n'y en a qu'un

        # Informations sur le compte
        print("Account ID:", my_account.accountId)#79cc3eb8-1d72-4e2a-bca7-8b87d6934417
        print("Type:", my_account.accountType)#MYRENAULT
        print("Status:", my_account.accountStatus)#ACTIVE
        print("First name:", persons.raw_data['firstName'])
        print("Last name:", persons.raw_data['lastName'])
        print("personId:", persons.raw_data['personId'])#7ededdb5-82a9-4ee8-a2cb-bf0c7c013cc7

        # Instanciation de l'objet correspondant au compte
        RenaultAccount = await client.get_api_account(my_account.accountId)
        print(RenaultAccount)

        # Récupération des véhicules
        vehicles_response  = await RenaultAccount.get_vehicles()
        first_vehicle = vehicles_response.vehicleLinks[0]
        print("VIN: ", first_vehicle.vin)      # Numéro de série (VIN)
        VIN = first_vehicle.vin

        # Instanciation de l'objet correspondant au véhicule
        RenaultVehicle = await RenaultAccount.get_api_vehicle(VIN)
        print(RenaultVehicle)

        # Récupération du niveau de la batterie
        battery = await RenaultVehicle.get_battery_status()
        print("Last update: ", format_date(str(battery.raw_data['timestamp'])))
        print("Niveau de batterie actuel:", battery.raw_data['batteryLevel'], "%")
        print("Autonomie restante:", battery.raw_data['batteryAutonomy'], "km")
        computed_max_autonomy = battery.raw_data['batteryAutonomy'] * (1 / battery.raw_data['batteryLevel']) * 100 
        print("Autonomie à 100% de charge", computed_max_autonomy)
        print("Plug status:", battery.raw_data['plugStatus'])
        print("Charging status:", battery.raw_data['chargingStatus'])
        chargingPower = 0
        print("Charging power:", chargingPower)

        # Récupération des infos cockpit
        cockpit = await RenaultVehicle._get_vehicle_data("cockpit")
        kilometrage = cockpit.raw_data['data']['attributes']['totalMileage']
        print("Kilométrage parcouru: ", kilometrage, "km")

        # Récupération de l'historique de recharges
        now = datetime.now(timezone.utc)
        start_date = now - timedelta(days=30)
        end_date = now - timedelta(days=0)
        charge_history = await RenaultVehicle.get_charges(start=start_date, end=end_date)

        # Statistiques globales de charge
        nb_charges = 0
        total_energy_charged = 0
        for charge in charge_history.raw_data['charges']:
            if charge['chargeEnergyRecovered'] == 0:
                continue
            nb_charges += 1
            total_energy_charged += charge['chargeEnergyRecovered']

        print("Nombre de charges:", nb_charges)
        print("Total énergie rechargée:", round(total_energy_charged, 2), "kWh")
        avg_consumption = round(total_energy_charged / (kilometrage / 100), 2)
        print("Consommation moyenne: ", avg_consumption, "kwh/100km")
        computed_remaining_autonomy = int(battery.raw_data['batteryLevel'] * USABLE_CAPACITY / avg_consumption)
        print("Autonomie restante (recalculée): ", computed_remaining_autonomy, "km")
        computed_max_autonomy_real = computed_remaining_autonomy * (1 / battery.raw_data['batteryLevel']) * 100 
        print("Autonomie restante réelle (recalculée): ", computed_max_autonomy_real, "km")

        # Affichage de l'historique de charges
        charges = charge_history.raw_data["charges"]#trier le dictionnaire par date de début de charge
        charges.sort(
            key=lambda x: datetime.fromisoformat(x['chargeStartDate'].replace("Z", "+00:00"))
        )

        custom_charges = []
        previous_end_level = None
        for charge in charge_history.raw_data['charges']:
            if charge['chargeEnergyRecovered'] == 0:
                continue

            chargeStartBatteryLevel = charge['chargeStartBatteryLevel']
            chargeEndBatteryLevel = charge['chargeEndBatteryLevel']
            chargeEnergyRecovered = charge['chargeEnergyRecovered']
            chargePercentRecovered = chargeEnergyRecovered / USABLE_CAPACITY * 100

            # Correction manuelle à appliquer sur les données boguées
            if (charge['chargeStartBatteryLevel'] == 0 or charge['chargeStartBatteryLevel'] == charge['chargeEndBatteryLevel']):
                chargeStartBatteryLevel = int(round(charge['chargeEndBatteryLevel'] - chargePercentRecovered, 0))

            # Affichage des données corrigées
            charge_str = str("chargeStartDate: " + format_date(str(charge['chargeStartDate']))) + ", chargeEndDate: " + format_date(str(charge['chargeEndDate']))
            charge_str += ", chargeStartBatteryLevel: " + str(int(round(chargeStartBatteryLevel))) + ", chargeEndBatteryLevel: " + str(int(round(chargeEndBatteryLevel)))
            charge_str += ", chargeEnergyRecovered: " + str(round(charge['chargeEnergyRecovered'], 2)) + "kWh (+" + str(round(chargePercentRecovered, 2)) + "%)"
            #print(charge_str)

            # Correction manuelle si charge < 1min on considère qu'elle a durée 1min et pas "0"
            charge_duration = charge['chargeDuration']
            if charge_duration == 0:
                charge_duration = 1

            # Calcul de la puissance de charge (kW)
            chargePower = chargeEnergyRecovered / (charge_duration / 60)
            # print("Puissance de recharge: ", round(chargePower, 2), "kW")

            # Correction manuelle : insertion manuelle de recharge manquante
            if previous_end_level is not None and chargeStartBatteryLevel > previous_end_level:
                percent_recovered = chargeStartBatteryLevel - previous_end_level
                missing_energy = percent_recovered / 100 * USABLE_CAPACITY
                
                custom_charges.append({
                    "chargeStartDate": shift_date(charge['chargeStartDate'], days=-1),
                    "chargeEndDate": shift_date(charge['chargeEndDate'], days=-1),
                    "chargeStartBatteryLevel": chargeStartBatteryLevel - percent_recovered,
                    "chargeEndBatteryLevel": chargeStartBatteryLevel,
                    "chargeEnergyRecovered": missing_energy,
                    "chargePercentRecovered": round((missing_energy / USABLE_CAPACITY * 100), 2),
                    "chargeDuration": DEFAULT_CHARGE_DURATION,
                    "chargePower": missing_energy / (DEFAULT_CHARGE_DURATION / 60),
                    "fakeCharge": True
                })

                nb_charges += 1
                total_energy_charged += missing_energy

            # Enregistrer les données corrigées et filtrées
            custom_charges.append({
                "chargeStartDate": charge['chargeStartDate'],
                "chargeEndDate": charge['chargeEndDate'],
                "chargeStartBatteryLevel": chargeStartBatteryLevel,
                "chargeEndBatteryLevel": chargeEndBatteryLevel,
                "chargeEnergyRecovered": chargeEnergyRecovered,
                "chargePercentRecovered": round(chargePercentRecovered, 2),
                "chargeDuration": charge_duration,
                "chargePower": chargePower,
                "fakeCharge": False
            })

            previous_end_level = chargeEndBatteryLevel

        # Récupération de la position GPS
        location = await RenaultVehicle._get_vehicle_data("location")
        gps_data = {
            "latitude": location.raw_data["data"]["attributes"]["gpsLatitude"],
            "longitude": location.raw_data["data"]["attributes"]["gpsLongitude"]
        }
        print("Longitude: ", gps_data['longitude'])
        print("Latitude: ", gps_data['latitude'])

        # Insérer toutes les données récoltées dans un dictionnaire pour affichage dans une application :
        data = {
            "VIN": VIN,
            "usable_capacity": USABLE_CAPACITY,
            "last_update": format_date(str(battery.raw_data['timestamp'])),
            "battery_level": battery.raw_data['batteryLevel'],
            "battery_autonomy": battery.raw_data['batteryAutonomy'],
            "battery_max_autonomy": int(round(computed_max_autonomy, 0)),
            "battery_autonomy_estimation": int(round(computed_remaining_autonomy, 0)),
            "battery_max_autonomy_real": int(round(computed_max_autonomy_real, 0)),
            "plugStatus": battery.raw_data['plugStatus'],
            "chargingStatus": battery.raw_data['chargingStatus'],
            "chargingRemainingTime": battery.raw_data['chargingRemainingTime'],
            "chargingPower": chargingPower,
            "kilometrage": kilometrage,
            "charge_stats": {
                "nb_charges": nb_charges,
                "total_energy_charged": round(total_energy_charged, 2),
                "avg_consumption": avg_consumption
            },
            "gps": gps_data,
            "charge_history": custom_charges,
            "assets":  first_vehicle.raw_data["vehicleDetails"]["assets"]
        }

        return data