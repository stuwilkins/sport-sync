import arrow
import logging
import yaml
from datetime import datetime
from withings_api.common import MeasureType

from fit import FitEncoder_Weight
from withings import WithingsData

logger = logging.getLogger("strava")
logger.setLevel(logging.DEBUG)


def get_config():
    with open('config.yml') as c:
        config = yaml.load(c, Loader=yaml.FullLoader)

    return config


def withings_sync(force=False):
    config = get_config()

    withings = WithingsData(credentials_file=".credentials")

    try:
        withings.load_credentials()
    except FileNotFoundError:
        pass

    withings.authenticate()

    weight = withings.get_measures(MeasureType.WEIGHT, arrow.utcnow().shift(days=-7))
    fat_ratio = withings.get_measures(MeasureType.FAT_RATIO, arrow.utcnow().shift(days=-7))
    hydration = withings.get_measures(MeasureType.HYDRATION, arrow.utcnow().shift(days=-7))
    bone_mass = withings.get_measures(MeasureType.BONE_MASS, arrow.utcnow().shift(days=-7))
    muscle_mass = withings.get_measures(MeasureType.MUSCLE_MASS, arrow.utcnow().shift(days=-7))

    # Now check if we need to update
    last_update = weight[1]

    logger.info('Last measurement at {}'.format(last_update))
    logger.info('Last update at {}'.format(config['nokia']['last_update']))

    # if (config['nokia']['last_update'] >= last_update) and not force:
    #     logger.info('No new weight updates')
    #     return

    msg = ''

    fit = FitEncoder_Weight()
    fit.write_file_info()
    fit.write_file_creator()
    fit.write_device_info(datetime.timestamp(datetime.now()))

    for w, fr in zip(weight, fat_ratio):
        print(w, fr)
    #     bmi = measure.weight / config['nokia']['height']**2

    #     msg += 'New measurement at {} ({})\n'.format(
    #         str(measure.date.datetime),
    #         measure.date.humanize())
    #     msg += 'New weight = {} kg\n'.format(measure.weight)
    #     msg += 'New fat ratio= {} %\n'.format(measure.fat_ratio)
    #     msg += 'New hydration = {} %\n'.format(measure.hydration)
    #     msg += 'New bone mass = {} kg\n'.format(measure.bone_mass)
    #     msg += 'New muscle mass = {} kg\n'.format(measure.muscle_mass)
    #     msg += 'Calculated BMI = {} kg.m^-2\n'.format(bmi)

    #             for m in msg.splitlines():
    #                 logger.info(m)

    #             # Sync Garmin

    #             logger.info('Syncing weight of {} with GARMIN.'
    #                         .format(measure.weight))

    #             fit.write_weight_scale(timestamp=measure.date.timestamp,
    #                                    weight=measure.weight,
    #                                    percent_fat=measure.fat_ratio,
    #                                    percent_hydration=measure.hydration,
    #                                    bone_mass=measure.bone_mass,
    #                                    muscle_mass=measure.muscle_mass,
    #                                    bmi=bmi)
    # fit.finish()

    # with GarminClient(config['garmin']['username'],
    #                   config['garmin']['password']) as client:
    #     client.upload_activity(io.BytesIO(fit.getvalue()), 'fit')

    # # Sync Strava

    # measure = measures[0]
    # ts = datetime.timestamp(datetime.now())
    # ts -= (config['nokia']['weight_int'] * 86400)
    # weight = [m.weight for m in measures if m.date.timestamp >= ts]

    # logger.info("Averaging {} weight measurements".format(len(weight)))

    # weight = mean(weight)

    # if (config['nokia']['last_update'] != measure.date.timestamp) or force:
    #     logger.info('Syncing weight of {} with STRAVA.'.format(measure.weight))
    #     strava = Strava(config['strava'])
    #     strava_token = strava.connect()
    #     config['strava'] = strava_token
    #     strava.client.update_athlete(weight=weight)

    #     msg += 'Synced weight of {} with Strava\n'.format(measure.weight)

    # config = get_config()
    # config['nokia']['last_update'] = max([m.date.timestamp for m in measures])
    # write_config(config)


if __name__ == "__main__":
    withings_sync()
