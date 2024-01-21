import arrow
from getpass import getpass
import io
import logging

from garminexport.garminclient import GarminClient


logger = logging.getLogger('garmin')
logger.setLevel(logging.DEBUG)


def get_activities(username, password, last_sync=0):

    data = list()

    with GarminClient(username, password) as client:

        activities = [list(act) for act in client.list_activities()
                      if act[1].timestamp() > last_sync]

        for act in activities:
            summary = client.get_activity_summary(act[0])
            fit_file = io.BytesIO(client.get_activity_fit(act[0]))
            data.append(
                tuple((
                    summary['activityName'],
                    summary['activityTypeDTO']['typeKey'],
                    fit_file
                ))
            )

    return data


if __name__ == "__main__":
    username = input("Username :")
    password = getpass("Password :")
    print(
        get_activities(
            username, password,
            arrow.utcnow().shift(days=-7).int_timestamp
        )
    )
