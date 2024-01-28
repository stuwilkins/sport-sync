import arrow
from dataclasses import dataclass
from oauthlib.common import to_unicode
from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import WebApplicationClient
from urllib import parse

import json
import pickle

# import logging
# import sys

# log = logging.getLogger("requests_oauthlib")
# log.addHandler(logging.StreamHandler(sys.stdout))
# log.setLevel(logging.DEBUG)

CREDENTIALS_FILE = "credentials.pickle"

STATUS_SUCCESS = (0,)

STATUS_AUTH_FAILED = (100, 101, 102, 200, 401)

STATUS_INVALID_PARAMS = (
    201,
    202,
    203,
    204,
    205,
    206,
    207,
    208,
    209,
    210,
    211,
    212,
    213,
    216,
    217,
    218,
    220,
    221,
    223,
    225,
    227,
    228,
    229,
    230,
    234,
    235,
    236,
    238,
    240,
    241,
    242,
    243,
    244,
    245,
    246,
    247,
    248,
    249,
    250,
    251,
    252,
    254,
    260,
    261,
    262,
    263,
    264,
    265,
    266,
    267,
    271,
    272,
    275,
    276,
    283,
    284,
    285,
    286,
    287,
    288,
    290,
    293,
    294,
    295,
    297,
    300,
    301,
    302,
    303,
    304,
    321,
    323,
    324,
    325,
    326,
    327,
    328,
    329,
    330,
    331,
    332,
    333,
    334,
    335,
    336,
    337,
    338,
    339,
    340,
    341,
    342,
    343,
    344,
    345,
    346,
    347,
    348,
    349,
    350,
    351,
    352,
    353,
    380,
    381,
    382,
    400,
    501,
    502,
    503,
    504,
    505,
    506,
    509,
    510,
    511,
    523,
    532,
    3017,
    3018,
    3019,
)

STATUS_UNAUTHORIZED = (214, 277, 2553, 2554, 2555)

STATUS_ERROR_OCCURRED = (
    215,
    219,
    222,
    224,
    226,
    231,
    233,
    237,
    253,
    255,
    256,
    257,
    258,
    259,
    268,
    269,
    270,
    273,
    274,
    278,
    279,
    280,
    281,
    282,
    289,
    291,
    292,
    296,
    298,
    305,
    306,
    308,
    309,
    310,
    311,
    312,
    313,
    314,
    315,
    316,
    317,
    318,
    319,
    320,
    322,
    370,
    371,
    372,
    373,
    374,
    375,
    383,
    391,
    402,
    516,
    517,
    518,
    519,
    520,
    521,
    525,
    526,
    527,
    528,
    529,
    530,
    531,
    533,
    602,
    700,
    1051,
    1052,
    1053,
    1054,
    2551,
    2552,
    2556,
    2557,
    2558,
    2559,
    3000,
    3001,
    3002,
    3003,
    3004,
    3005,
    3006,
    3007,
    3008,
    3009,
    3010,
    3011,
    3012,
    3013,
    3014,
    3015,
    3016,
    3020,
    3021,
    3022,
    3023,
    3024,
    5000,
    5001,
    5005,
    5006,
    6000,
    6010,
    6011,
    9000,
    10000,
)

STATUS_TIMEOUT = (522,)
STATUS_BAD_STATE = (524,)
STATUS_TOO_MANY_REQUESTS = (601,)


def save_credentials(credentials):
    """Save credentials to a file."""
    print("Saving")
    with open(CREDENTIALS_FILE, "wb") as file_handle:
        pickle.dump(credentials, file_handle)


def load_credentials():
    """Load credentials from a file."""
    print("Using credentials saved in:", CREDENTIALS_FILE)
    with open(CREDENTIALS_FILE, "rb") as file_handle:
        return pickle.load(file_handle)


def adjust_withings_token(response):
    """Restructures token from withings response"""
    try:
        token = json.loads(response.text)
    except Exception:  # pylint: disable=broad-except
        # If there was exception, just return unmodified response
        return response
    status = token.pop("status", 0)
    if status:
        # Set the error to the status
        token["error"] = 0
    body = token.pop("body", None)
    if body:
        # Put body content at root level
        token.update(body)
    # pylint: disable=protected-access
    response._content = to_unicode(json.dumps(token)).encode("UTF-8")

    return response


class StatusException(Exception):
    """Status exception."""

    def __init__(self, status):
        """Create instance."""
        super().__init__("Error code %s" % str(status))


class UnknownStatusException(StatusException):
    """Unknown status code but it's still not successful."""


@dataclass(frozen=True)
class WithingsCredentials:
    """Withings API Credentials"""

    client_id: str
    client_secret: str
    redirect_uri: str
    access_token: str = ""
    token_expiry: int = 0
    token_type: str = ""
    refresh_token: str = ""
    userid: int = 0
    expires_in: int = 0


@dataclass
class WithingsMeasureScaleGroup:
    """Withings Measure Values"""

    timestamp: None
    weight: float = 0.0
    muscle_mass: float = 0.0
    bone_mass: float = 0.0
    fat_mass: float = 0.0
    fat_free_mass: float = 0.0
    fat_ratio: float = 0.0

    def __init__(self, group, timezone=None):
        self.from_measure_group(group, timezone)

    def from_measure_group(self, group, timezone=None):
        # Set timestamp

        self.timestamp = arrow.Arrow.fromtimestamp(group["date"], tzinfo=timezone)

        for measure in group["measures"]:
            if measure["type"] == 1:
                self.weight = self._measure_to_val(measure)
            if measure["type"] == 76:
                self.muscle_mass = self._measure_to_val(measure)
            if measure["type"] == 88:
                self.bone_mass = self._measure_to_val(measure)
            if measure["type"] == 8:
                self.fat_mass = self._measure_to_val(measure)
            if measure["type"] == 5:
                self.fat_free_mass = self._measure_to_val(measure)
            if measure["type"] == 6:
                self.fat_ratio = self._measure_to_val(measure)

    def _measure_to_val(self, measure):
        return float(measure["value"] * pow(10, measure["unit"]))


@dataclass
class WithingsMeasureHeightGroup:
    """Withings Measure Values"""

    timestamp: None
    height: float = 0

    def __init__(self, group, timezone=None):
        self.from_measure_group(group, timezone)

    def from_measure_group(self, group, timezone=None):
        # Set timestamp

        self.timestamp = arrow.Arrow.fromtimestamp(group["date"], tzinfo=timezone)

        for measure in group["measures"]:
            if measure["type"] == 4:
                self.height = self._measure_to_val(measure)

    def _measure_to_val(self, measure):
        return float(measure["value"] * pow(10, measure["unit"]))


class WithingsAPI:
    def __init__(self, credentials):
        self._session = None
        self._scope = ["user.metrics"]
        self._credentials = credentials
        self._token = {
            "access_token": self._credentials.access_token,
            "refresh_token": self._credentials.refresh_token,
            "token_type": self._credentials.token_type,
            "expires_in": self._credentials.expires_in,
        }

    def authenticate(self):
        """Authenticate to withings API"""
        self._session = OAuth2Session(
            self._credentials.client_id,
            token=self._token,
            client=WebApplicationClient(  # nosec
                self._credentials.client_id,
                token=self._token,
                default_token_placement="query",
            ),
            auto_refresh_url="https://wbsapi.withings.net/v2/oauth2",
            auto_refresh_kwargs={
                "action": "requesttoken",
                "client_id": self._credentials.client_id,
                "client_secret": self._credentials.client_secret,
            },
            redirect_uri=self._credentials.redirect_uri,
            # scope=self._scope,
            token_updater=self._token_updater,
        )

        self._session.register_compliance_hook(
            "access_token_response", adjust_withings_token
        )
        self._session.register_compliance_hook(
            "refresh_token_response", adjust_withings_token
        )

        # self.get_auth_code()
        self.refresh_token()

    def refresh_token(self):
        """Manually refresh the oauth token"""
        token = self._session.refresh_token(token_url=self._session.auto_refresh_url)
        self._token_updater(token=token)

    def _token_updater(self, token):
        """Update and set the oauth token"""
        self._credentials = WithingsCredentials(
            access_token=token["access_token"],
            expires_in=token["expires_in"],
            token_type=self._credentials.token_type,
            refresh_token=token["refresh_token"],
            userid=self._credentials.userid,
            client_id=self._credentials.client_id,
            client_secret=self._credentials.client_secret,
            redirect_uri=self._credentials.redirect_uri,
        )
        save_credentials(self._credentials)

    def get_auth_code(self):
        """Follow oauth2 flow and get authorization code"""
        authorization_url, state = self._session.authorization_url(
            "https://account.withings.com/oauth2_user/authorize2",
        )

        authorization_url += "&scope=user.metrics"

        print("Please go to : {}".format(authorization_url))
        authorization_response = input("Enter the full callback URL :")

        redirected_uri_params = dict(
            parse.parse_qsl(parse.urlsplit(authorization_response).query)
        )
        auth_code = redirected_uri_params["code"]

        token = self._session.fetch_token(
            "https://wbsapi.withings.net/v2/oauth2",
            include_client_id=True,
            action="requesttoken",
            code=auth_code,
            client_id=client_id,
            client_secret=client_secret,
        )

    def _get_data(self, url, data):
        """Get data and check response"""
        r = self._session.post(url, data=data)
        if r.status_code != 200:
            raise RuntimeError

        response = r.json()
        status = response.get("status")

        if status is None:
            raise UnknownStatusException(status=status)

        if status in STATUS_SUCCESS:
            return response.get("body")

        raise UnknownStatusException(status=status)

    def get_measures(self, lastupdate):
        data = {
            "action": "getmeas",
            "meastypes": "1,5,6,8,76,77,88",
            "category": "1",
            "lastupdate": lastupdate.int_timestamp,
        }

        response = self._get_data("https://wbsapi.withings.net/v2/measure", data=data)

        val = list()
        if "measuregrps" in response:
            for group in response["measuregrps"]:
                val.append(WithingsMeasureScaleGroup(group, response["timezone"]))

        return val

    def get_height(self, lastupdate):
        data = {
            "action": "getmeas",
            "meastype": "4",
            "category": "1",
            "lastupdate": lastupdate.int_timestamp,
        }

        response = self._get_data("https://wbsapi.withings.net/v2/measure", data=data)

        val = list()
        if "measuregrps" in response:
            for group in response["measuregrps"]:
                val.append(WithingsMeasureHeightGroup(group, response["timezone"]))

        return val


if __name__ == "__main__":
    api = WithingsAPI(load_credentials())
    api.authenticate()
    print(api.get_measures(arrow.utcnow().shift(days=-31)))
    print(api.get_height(arrow.Arrow.fromtimestamp(0)))
