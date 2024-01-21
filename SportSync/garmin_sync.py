# -*- coding: utf-8 -*-
import time
import io
import sys
import yaml
import logging
import smtplib
import traceback
from datetime import datetime

from statistics import mean
from garminexport.garminclient import GarminClient
from stravalib.client import Client
from stravalib.exc import ActivityUploadFailed
from nokia import NokiaAuth, NokiaApi, NokiaCredentials
from fit import FitEncoder_Weight
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger('garmin_sync')
logger.setLevel(logging.DEBUG)


def get_config():
    with open('config.yml') as c:
        config = yaml.load(c, Loader=yaml.FullLoader)

    return config


def write_config(config):
    with open('config.yml', 'w') as outfile:
        yaml.dump(config, outfile, default_flow_style=False)


def send_email(subject, message):

    config = get_config()['email']

    s = smtplib.SMTP(host=config['host'], port=config['port'])
    s.starttls()
    s.login(config['email'], config['password'])

    msg = MIMEMultipart()
    msg['From'] = config['email']
    msg['To'] = config['to']
    msg['Subject'] = subject

    msg.attach(MIMEText(message, 'plain'))
    s.send_message(msg)


def nokia_refresh_cb(token):
    access_token = token['access_token']
    refresh_token = token['refresh_token']
    token_type = token['token_type']
    expires_in = token['expires_in']

    logger.debug('refresh_cb called')
    logger.debug('access_token = {}'.format(access_token))
    logger.debug('refresh_token = {}'.format(refresh_token))
    logger.debug('token_type = {}'.format(token_type))
    logger.debug('expires_in = {}'.format(expires_in))

    config = get_config()

    ts = datetime.timestamp(datetime.now())

    config['nokia']['access_token'] = access_token
    config['nokia']['refresh_token'] = refresh_token
    config['nokia']['token_type'] = token_type
    config['nokia']['token_expiry'] = ts + expires_in

    write_config(config)


class Strava:
    def __init__(self, token):
        self._token = token
        self._client = None
        self._verbose = True

    def connect(self):
        self._client = Client()
        token = self._token

        refresh_response = self._client.refresh_access_token(
            client_id=token['client_id'],
            client_secret=token['client_secret'],
            refresh_token=token['refresh_token'])

        token.update(refresh_response)
        self._token = token

        athlete = self._client.get_athlete()
        if self._verbose:
            logger.info("Connected to STRAVA as athelete \"{} {}\"".format(
                athlete.firstname, athlete.lastname))

        return self._token

    def set_weight(self, weight):
        self._client.update_athlete(weight=weight)

    @property
    def client(self):
        return self._client


def strava_sync():
    config = get_config()

    last_sync = config['main']['last_sync']

    # Do garmin connect part

    with GarminClient(config['garmin']['username'],
                      config['garmin']['password']) as client:

        activities = [list(act) for act in client.list_activities()
                      if act[1].timestamp() > last_sync]

        dates = [a[1] for a in activities]
        numbers = [a[0] for a in activities]

        fit_files = [io.BytesIO(client.get_activity_fit(n)) for n in numbers]
        summary = [client.get_activity_summary(n) for n in numbers]
        names = [s['activityName'] for s in summary]
        types = [s['activityTypeDTO']['typeKey'] for s in summary]

    if len(fit_files):

        logger.info('Uploading {} activities to STRAVA'.format(len(fit_files)))

        # Now do Strava Part

        strava = Strava(config['strava'])
        strava_token = strava.connect()

        # Write out config for token
        config['strava'] = strava_token
        write_config(config)

        upload_types = config['strava']['upload_types']

        for n, t, f in zip(names, types, fit_files):
            if t in upload_types:
                logger.info('Uploading {} type {}'.format(n, t))

                loader = strava.client.upload_activity(f, 'fit', n)
                try:
                    loader.wait()
                except ActivityUploadFailed as e:
                    logger.critical('Failed to upload activity \"{}\" {}'
                                    .format(n, str(e)))
                else:
                    logger.info('Uploaded activity \"{}\"'.format(n))

            else:
                logger.info('Skipped activity type \"{}\" for activity {}'
                            .format(t, n))

        # Now store last timestamp

        config['main']['last_sync'] = max(dates).timestamp()
        write_config(config)


def nokia_sync(force=False):
    config = get_config()

    n = config['nokia']
    creds = NokiaCredentials(n['access_token'],
                             n['token_expiry'],
                             n['token_type'],
                             n['refresh_token'],
                             n['user_id'],
                             n['client_id'],
                             n['consumer_secret'])

    nokia_client = NokiaApi(creds, refresh_cb=nokia_refresh_cb)

    measures = nokia_client.get_measures()
    measure = measures[0]

    logger.info('Recieved {} measurements'.format(len(measures)))

    # Now check if we need to update
    last_update = max([m.date.timestamp for m in measures])

    logger.info('Last measurement at {}'.format(last_update))
    logger.info('Last update at {}'.format(config['nokia']['last_update']))

    if (config['nokia']['last_update'] >= last_update) and not force:
        logger.info('No new weight updates')
        return measures

    msg = ''

    fit = FitEncoder_Weight()
    fit.write_file_info()
    fit.write_file_creator()
    fit.write_device_info(datetime.timestamp(datetime.now()))

    for measure in measures:
        if (config['nokia']['last_update'] < measure.date.timestamp) or force:

            if measure.weight is not None:
                bmi = measure.weight / config['nokia']['height']**2

                msg += 'New measurement at {} ({})\n'.format(
                    str(measure.date.datetime),
                    measure.date.humanize())

                msg += 'New weight = {} kg\n'.format(measure.weight)
                msg += 'New fat ratio= {} %\n'.format(measure.fat_ratio)
                msg += 'New hydration = {} %\n'.format(measure.hydration)
                msg += 'New bone mass = {} kg\n'.format(measure.bone_mass)
                msg += 'New muscle mass = {} kg\n'.format(measure.muscle_mass)
                msg += 'Calculated BMI = {} kg.m^-2\n'.format(bmi)

                for m in msg.splitlines():
                    logger.info(m)

                # Sync Garmin

                logger.info('Syncing weight of {} with GARMIN.'
                            .format(measure.weight))

                fit.write_weight_scale(timestamp=measure.date.timestamp,
                                       weight=measure.weight,
                                       percent_fat=measure.fat_ratio,
                                       percent_hydration=measure.hydration,
                                       bone_mass=measure.bone_mass,
                                       muscle_mass=measure.muscle_mass,
                                       bmi=bmi)

    fit.finish()

    with GarminClient(config['garmin']['username'],
                      config['garmin']['password']) as client:
        client.upload_activity(io.BytesIO(fit.getvalue()), 'fit')

    # Sync Strava

    measure = measures[0]
    ts = datetime.timestamp(datetime.now())
    ts -= (config['nokia']['weight_int'] * 86400)
    weight = [m.weight for m in measures if m.date.timestamp >= ts]

    logger.info("Averaging {} weight measurements".format(len(weight)))

    weight = mean(weight)

    if (config['nokia']['last_update'] != measure.date.timestamp) or force:
        logger.info('Syncing weight of {} with STRAVA.'.format(measure.weight))
        strava = Strava(config['strava'])
        strava_token = strava.connect()
        config['strava'] = strava_token
        strava.client.update_athlete(weight=weight)

        msg += 'Synced weight of {} with Strava\n'.format(measure.weight)

    config = get_config()
    config['nokia']['last_update'] = max([m.date.timestamp for m in measures])
    write_config(config)

    send_email('New Weight Sync', msg)

    return measures


def main():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO)
    try:
        logger.info("Starting strava_sync()")
        strava_sync()
    except Exception:
        logger.error("Error processing strava_sync()")
        exc = sys.exc_info()
        send_email('Error processing strava_sync()',
                   ''.join(traceback.format_exception(*exc)))
        print(''.join(traceback.format_exception(*exc)),
              file=sys.stderr)

    try:
        logger.info("Starting nokia_sync()")
        nokia_sync()
    except Exception:
        logger.error("Error processing nokia_sync()")
        exc = sys.exc_info()
        send_email('Error Processing nokia_sync()',
                   ''.join(traceback.format_exception(*exc)))
        print(''.join(traceback.format_exception(*exc)),
              file=sys.stderr)


if __name__ == '__main__':
    main()
