import arrow
import logging
import yaml
from datetime import datetime

import garth
import io
from statistics import mean
from .withings import WithingsAPI
from .strava import Strava

from .fit import FitEncoderWeight

logger = logging.getLogger(__name__)


def write_config(config):
    with open("config.yml", "w") as outfile:
        yaml.dump(config, outfile, default_flow_style=False)


def get_config():
    with open("config.yml") as c:
        config = yaml.load(c, Loader=yaml.Loader)

    return config


def update_config(credentials, config):
    config["withings"] = credentials


def withings_sync(force=False):
    config = get_config()

    withings = WithingsAPI(
        config["withings"], save_callback=update_config, save_callback_args=(config,)
    )
    withings.authenticate()

    garth_api = garth.Client(domain="garmin.com")
    garth_api.loads(config["garth"])
    # garth_api.loads('~/.garth')

    # garth_api.login(config['garmin']['username'],
    #                 config['garmin']['password'])
    #
    # config['garth'] = garth_api.dumps()
    # write_config(config)

    scale_data = withings.get_measures(arrow.utcnow().shift(days=-21))
    scale_height = withings.get_height(arrow.Arrow.fromtimestamp(0))

    # Now check if we need to update
    last_update = scale_data[-1].timestamp.int_timestamp

    logger.info("Last measurement at {}".format(last_update))
    logger.info("Last update at {}".format(config["nokia"]["last_update"]))

    if (config["nokia"]["last_update"] >= last_update) and not force:
        logger.info("No new weight updates")
        return

    fit = FitEncoderWeight()
    fit.write_file_info()
    fit.write_file_creator()

    for measure in scale_data:

        bmi = measure.weight / scale_height[-1].height ** 2

        logger.info(
            "New measurement {} ({})".format(
                measure.timestamp.format(), measure.timestamp.humanize()
            )
        )
        logger.info("New weight = {} kg".format(measure.weight))
        logger.info("New fat ratio= {} %".format(measure.fat_ratio))
        logger.info("New hydration = {} %".format(measure.hydration))
        logger.info("New bone mass = {} kg".format(measure.bone_mass))
        logger.info("New muscle mass = {} kg".format(measure.muscle_mass))
        logger.info("Calculated BMI = {} kg.m^-2".format(bmi))

        # Sync Garmin

        fit.write_device_info(timestamp=measure.timestamp.int_timestamp)
        fit.write_weight_scale(
            timestamp=measure.timestamp.int_timestamp,
            weight=measure.weight,
            percent_fat=measure.fat_ratio,
            percent_hydration=measure.hydration,
            bone_mass=measure.bone_mass,
            muscle_mass=measure.muscle_mass,
            bmi=bmi,
        )
    fit.finish()

    data = io.BytesIO(fit.getvalue())
    data.name = "withings.fit"

    garth_api.upload(data)

    # Sync Strava

    ts = datetime.timestamp(datetime.now())
    ts -= config["nokia"]["weight_int"] * 86400

    weight = [m.weight for m in scale_data if m.timestamp.int_timestamp >= ts]
    logger.info("Averaging {} weight measurements".format(len(weight)))
    weight = mean(weight)

    measure_time = max(
        [
            m.timestamp.int_timestamp
            for m in scale_data
            if m.timestamp.int_timestamp >= ts
        ]
    )

    if (config["nokia"]["last_update"] <= measure_time) or force:
        logger.info("Syncing weight of {} with STRAVA.".format(measure.weight))
        strava = Strava(config["strava"])
        strava_token = strava.connect()
        config["strava"] = strava_token
        strava.client.update_athlete(weight=weight)

        logger.info("Synced weight of {} with Strava".format(measure.weight))

    config = get_config()
    config["nokia"]["last_update"] = max(
        [m.timestamp.int_timestamp for m in scale_data]
    )

    write_config(config)
