import time
import io
import datetime
import yaml

from garminexport.garminclient import GarminClient

from stravalib.client import Client
from stravalib.exc import ActivityUploadFailed

from nokia import NokiaAuth, NokiaApi, NokiaCredentials

from fit import FitEncoder_Weight

upload_types = ['running']

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
            print("Connected to STRAVA as athelete \"{} {}\"".format(
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

        print('Uploading {} activities to STRAVA'.format(len(fit_files)))

        config['main']['last_sync'] = max(dates).timestamp()

        # Now do Strava Part

        strava = Strava(config['strava'])
        strava_token = strava.connect()

        for n, t, f in zip(names, types, fit_files):
            if t in upload_types:
                print('Uploading {} type {}'.format(n, t))

                loader = strava.client.upload_activity(f, 'fit', n)
                try:
                    loader.wait()
                except ActivityUploadFailed as e:
                    print('Failed to upload activity \"{}\" {}'
                        .format(n, str(e)))
                else:
                    print('Uploaded activity \"{}\"'.format(n))

        config['strava'] = strava_token

    # Now write out YAML file

    with open('config.yml', 'w') as outfile:
        yaml.dump(config, outfile, default_flow_style=False)

def nokia_sync():
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

    nokia_client = NokiaApi(creds)

    measure = nokia_client.get_measures(limit=1)[0]

    creds = nokia_client.get_credentials()
    config['nokia']['access_token'] = creds.access_token
    config['nokia']['token_expiry'] = creds.token_expiry
    config['nokia']['token_type'] = creds.token_type
    config['nokia']['refresh_token'] = creds.refresh_token
    config['nokia']['user_id'] = creds.user_id
    config['nokia']['client_id'] = creds.client_id
    config['nokia']['consumer_secret'] = creds.consumer_secret

    if config['nokia']['last_update'] != measure.date.timestamp:

        # Sync Strava

        strava = Strava(config['strava'])
        strava_token = strava.connect()
        config['strava'] = strava_token
        strava.client.update_athlete(weight=measure.weight)

        # Sync Garmin

        fit = FitEncoder_Weight()
        fit.write_file_info()
        fit.write_file_creator()
        fit.write_device_info(timestamp=measure.date.timestamp)
        fit.write_weight_scale(timestamp=measure.date.timestamp,
                               weight=measure.weight)
        fit.finish()

        with GarminClient(config['garmin']['username'],
                          config['garmin']['password']) as client:
            client.upload_activity(io.BytesIO(fit.getvalue()), 'fit')

        config['nokia']['last_update'] = measure.date.timestamp

    with open('config.yml', 'w') as outfile:
        yaml.dump(config, outfile, default_flow_style=False)

if __name__ == '__main__':
    strava_sync()
    nokia_sync()
