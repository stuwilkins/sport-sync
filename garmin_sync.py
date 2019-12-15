# -*- coding: utf-8 -*-
import time
import io
import sys
import datetime
import yaml
import logging
import smtplib
import traceback

from garminexport.garminclient import GarminClient
from stravalib.client import Client
from stravalib.exc import ActivityUploadFailed
from nokia import NokiaAuth, NokiaApi, NokiaCredentials
from fit import FitEncoder_Weight
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger('garmin_sync')
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

ch = logging.StreamHandler(sys.stderr)
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)

fh = logging.FileHandler(filename='sync.log')
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)

logging.getLogger('garminexport.garminclient').addHandler(fh)
logging.getLogger('garminexport.garminclient').setLevel(logging.DEBUG)
logging.getLogger('stravalib.client').addHandler(fh)
logging.getLogger('stravalib.client').setLevel(logging.DEBUG)
logging.getLogger('requests_oauthlib').addHandler(fh)
logging.getLogger('requests_oauthlib').setLevel(logging.DEBUG)
logging.getLogger('oauthlib.oauth2').addHandler(fh)
logging.getLogger('oauthlib.oauth2').setLevel(logging.DEBUG)


def send_email(subject, message):
    with open('config.yml') as c:
        config = yaml.load(c, Loader=yaml.FullLoader)

    config = config['email']

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
    with open('config.yml') as c:
        config = yaml.load(c, Loader=yaml.FullLoader)

    last_sync = config['main']['last_sync']

    #now = datetime.datetime.now(datetime.timezone.utc)
    #now -= datetime.timedelta(days=5)
    #last_sync = now.timestamp()

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

        config['main']['last_sync'] = max(dates).timestamp()

        # Now do Strava Part

        strava = Strava(config['strava'])
        strava_token = strava.connect()

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
                logger.info('Skipped activity type \"{}\" for activity {}'.format(t, n))

        config['strava'] = strava_token

    # Now write out YAML file

    with open('config.yml', 'w') as outfile:
        yaml.dump(config, outfile, default_flow_style=False)

def nokia_sync(force=False):
    with open('config.yml') as c:
        config = yaml.load(c, Loader=yaml.FullLoader)

    n = config['nokia']

    creds = NokiaCredentials(n['access_token'],
                             n['token_expiry'],
                             n['token_type'],
                             n['refresh_token'],
                             n['user_id'],
                             n['client_id'],
                             n['consumer_secret'])

    nokia_client = NokiaApi(creds, refresh_cb=nokia_refresh_cb)

    measure = nokia_client.get_measures(limit=1)[0]

    creds = nokia_client.get_credentials()

    config['nokia']['access_token'] = creds.access_token
    config['nokia']['token_expiry'] = creds.token_expiry
    config['nokia']['token_type'] = creds.token_type
    config['nokia']['refresh_token'] = creds.refresh_token
    config['nokia']['user_id'] = creds.user_id
    config['nokia']['client_id'] = creds.client_id
    config['nokia']['consumer_secret'] = creds.consumer_secret

    if (config['nokia']['last_update'] != measure.date.timestamp) or force:
        msg = ''

        msg += 'New measurement at {} ({})\n\n'.format(
                str(measure.date.datetime),
                measure.date.humanize())

        msg += 'New weight = {} kg\n'.format(measure.weight)
        msg += 'New fat ratio= {} %\n'.format(measure.fat_ratio)
        msg += 'New hydration = {} %\n'.format(measure.hydration)
        msg += 'New bone mass = {} kg\n'.format(measure.bone_mass)
        msg += 'New muscle mass = {} kg\n'.format(measure.muscle_mass)

        for m in msg.splitlines():
            logger.info(m)

        # Sync Strava

        logger.info('Syncing weight of {} with STRAVA.'.format(measure.weight))
        strava = Strava(config['strava'])
        strava_token = strava.connect()
        config['strava'] = strava_token
        strava.client.update_athlete(weight=measure.weight)

        # Sync Garmin

        logger.info('Syncing weight of {} with GARMIN.'.format(measure.weight))

        fit = FitEncoder_Weight()
        fit.write_file_info()
        fit.write_file_creator()
        
        fit.write_device_info(timestamp=measure.date.timestamp)
        fit.write_weight_scale(timestamp=measure.date.timestamp,
                               weight=measure.weight,
                               percent_fat=measure.fat_ratio,
                               percent_hydration=measure.hydration,
                               bone_mass=measure.bone_mass,
                               muscle_mass=measure.muscle_mass)
        fit.finish()

        with GarminClient(config['garmin']['username'],
                          config['garmin']['password']) as client:
            client.upload_activity(io.BytesIO(fit.getvalue()), 'fit')

        config['nokia']['last_update'] = measure.date.timestamp

        send_email('New Weight Reading', msg)

    else:
        logger.info("Weight of {} already synced.".format(measure.weight))

    with open('config.yml', 'w') as outfile:
        yaml.dump(config, outfile, default_flow_style=False)

    return measure

if __name__ == '__main__':
    try:
        logger.info("Starting strava_sync()")
        strava_sync()
    except:
        logger.error("Error processing strava_sync()")
        exc = sys.exc_info()
        send_email('Error processing strava_sync()', 
                ''.join(traceback.format_exception(*exc)))

    try:
        logger.info("Starting nokia_sync()")
        nokia_sync()
    except:
        logger.error("Error processing nokia_sync()")
        exc = sys.exc_info()
        send_email('Error Processing nokia_sync()',
                ''.join(traceback.format_exception(*exc)))
