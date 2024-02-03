import yaml
from urllib import parse
from stravalib.client import Client


def get_config():
    with open("config.yml") as c:
        config = yaml.load(c, Loader=yaml.FullLoader)

    return config


def write_config(config):
    with open("config.yml", "w") as outfile:
        yaml.dump(config, outfile, default_flow_style=False)


def login():
    config = get_config()

    client = Client()

    url = client.authorization_url(
        client_id=config["strava"]["client_id"],
        redirect_uri="http://www.stuwilkins.org",
        scope=[
            "read_all",
            "profile:read_all",
            "activity:read_all",
            "profile:write",
            "activity:write",
        ],
    )

    print(f"To authenticate, please go to {url}")

    authorization_response = input("Enter the full callback URL :")

    redirected_uri_params = dict(
        parse.parse_qsl(parse.urlsplit(authorization_response).query)
    )
    auth_code = redirected_uri_params["code"]

    access_token = client.exchange_code_for_token(
        client_id=config["strava"]["client_id"],
        client_secret=config["strava"]["client_secret"],
        code=auth_code,
    )

    config["strava"].update(access_token)
    write_config(config)


if __name__ == "__main__":
    login()
