import pickle
from typing import cast, Union
from urllib import parse

import arrow
import datetime
from typing_extensions import Final
from withings_api import AuthScope, WithingsApi, WithingsAuth
from withings_api.common import (
    CredentialsType,
    MeasureType,
    query_measure_groups,
    AuthFailedException,
)


DateType = Union[arrow.Arrow, datetime.date, datetime.datetime, int, str]


class WithingsData:
    def __init__(self, credentials_file=".credentials"):
        self.credentials_file = credentials_file
        self.credentials = None
        self.api = None
        self.client_id = None
        self.consumer_secret = None
        self.callback_uri = None

    def save_credentials(self):
        """Save credentials to a file."""
        print("Saving credentials in:", self.credentials_file)
        with open(self.credentials_file, "wb") as file_handle:
            pickle.dump(self.credentials, file_handle)
            pickle.dump(self.callback_uri, file_handle)

    def load_credentials(self):
        """Load credentials from a file."""
        print("Using credentials saved in:", self.credentials_file)
        with open(self.credentials_file, "rb") as file_handle:
            self.credentials = cast(CredentialsType, pickle.load(file_handle))
            self.callback_uri = pickle.load(file_handle)

        self.client_id = self.credentials.client_id
        self.consumer_secret = self.credentials.consumer_secret

    def authenticate(self):
        """Authenticate to the Withings API"""
        if self.credentials is not None:
            api = WithingsApi(self.credentials, refresh_cb=self.save_credentials)
            try:
                api.user_get_device()
            except AuthFailedException:
                self.credentials = None
                print("Credentials in file are expired. Re-starting auth procedure...")

        if self.credentials is None:
            print("Attempting to get credentials...")
            auth: Final = WithingsAuth(
                client_id=self.client_id,
                consumer_secret=self.consumer_secret,
                callback_uri=self.callback_uri,
                scope=(
                    AuthScope.USER_ACTIVITY,
                    AuthScope.USER_METRICS,
                    AuthScope.USER_INFO,
                    AuthScope.USER_SLEEP_EVENTS,
                ),
            )

            authorize_url: Final = auth.get_authorize_url()
            print("Goto this URL in your browser and authorize:", authorize_url)
            print(
                "Once you are redirected, copy and paste the whole url"
                "(including code) here."
            )
            redirected_uri: Final = input("Provide the entire redirect uri: ")
            redirected_uri_params: Final = dict(
                parse.parse_qsl(parse.urlsplit(redirected_uri).query)
            )
            auth_code: Final = redirected_uri_params["code"]

            print("Getting credentials with auth code", auth_code)
            self.credentials = auth.get_credentials(auth_code)
            self.save_credentials()

        self.api = WithingsApi(self.credentials, refresh_cb=self.save_credentials)

    def get_latest_measure(self, meastype: MeasureType, lastupdate: DateType):
        """Get measures from API"""
        meas_result = self.api.measure_get_meas(
            meastype=meastype, lastupdate=lastupdate, startdate=None, enddate=None
        )
        groups = query_measure_groups(meas_result)

        if len(groups) < 1:
            return None

        if len(groups[-1].measures) < 1:
            return None

        measure = groups[-1].measures[-1]
        timestamp = groups[-1].date.int_timestamp
        val = float(measure.value * pow(10, measure.unit))

        return tuple((val, timestamp))


if __name__ == "__main__":
    withings = WithingsData(credentials_file=".credentials")

    try:
        withings.load_credentials()
    except FileNotFoundError:
        pass

    withings.authenticate()

    print(
        withings.get_latest_measure(MeasureType.WEIGHT, arrow.utcnow().shift(days=-7))
    )
    print(
        withings.get_latest_measure(
            MeasureType.FAT_RATIO, arrow.utcnow().shift(days=-7)
        )
    )
    print(
        withings.get_latest_measure(
            MeasureType.HYDRATION, arrow.utcnow().shift(days=-7)
        )
    )
    print(
        withings.get_latest_measure(
            MeasureType.BONE_MASS, arrow.utcnow().shift(days=-7)
        )
    )
    print(
        withings.get_latest_measure(
            MeasureType.MUSCLE_MASS, arrow.utcnow().shift(days=-7)
        )
    )
