import logging

from stravalib.client import Client


logger = logging.getLogger("strava")
logger.setLevel(logging.DEBUG)


class Strava:
    def __init__(self, token):
        self._token = token
        self._client = None
        self._verbose = True

    def connect(self):
        self._client = Client()
        token = self._token

        refresh_response = self._client.refresh_access_token(
            client_id=token["client_id"],
            client_secret=token["client_secret"],
            refresh_token=token["refresh_token"],
        )

        token.update(refresh_response)
        self._token = token

        athlete = self._client.get_athlete()
        if self._verbose:
            logger.info(
                'Connected to STRAVA as athelete "{} {}"'.format(
                    athlete.firstname, athlete.lastname
                )
            )

        return self._token

    def set_weight(self, weight):
        self._client.update_athlete(weight=weight)

    @property
    def client(self):
        return self._client
