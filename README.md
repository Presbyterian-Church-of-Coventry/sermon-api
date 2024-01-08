# Python for PCC

If you would like to run the uploading scripts manually, you can clone this repo, `cd` into the directory, and

```
pip3 install -r requirements.txt
```

Generate an API key with

```
python3 main.py -key
```

or simply edit `data/api.txt`.

Then run the API with

```
python3 main.py -a
```

You can find an example of a frontend for the API we actually use in [upload.vue](examples/Upload.vue). I'd recommend pulling the Docker image from `coventrypca/sermon-api:latest`, or you could clone this repository and build it yourself with `docker build .`.

To authenticate with Google and upload to Youtube, you'll need to generate OAuth2 credentials [here](https://console.cloud.google.com/projectcreate) with Youtube API access. Download the `client_secrets.json` file and bind the file to `/app/data/client_secrets.json`. First, though, you must run

```
python3 main.py -auth
```

with your `client_secrets.json` file in the data directory on your local machine. This will open a webpage where you can authenticate your channel, which will generate an `oauth2.json` file you need to bind to `/app/data/oauth2.json` on your Docker container. This will keep the container permenantly authenticated.

If you would like to run the API on bare metal, rename `.env_example` to `.env` and fill the variables in there, then run `python3 main.py -a`.

Use the [Docker Compose File](docker-compose.yml) as a guide for filling in all the nessecary environment variables. See the chart below for further descriptions:

| Env Variable  | Comment                                                                                                                                    |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| SA_API_KEY    | Your SermonAudio API Key. You can find it by signing in and going [here](https://www.sermonaudio.com/secure/members_stats.asp)             |
| S3_ACCESS_KEY | Get your access token for your S3 storage if you have it. If not, don't supply it and this part won't run                                  |
| S3_SECRET     | Same as above, but use your secret token here. You could also use Docker secrets as this is sensitive                                      |
| CHANNEL_ID    | Supply the _ID_ of the channel you would like to scrape for latest video to scrub through on the web interface.                            |

Enjoy! If anyone else ever tries to use this it'll need to be customized a great deal, but the upload pipelines should be ironed out at the very least. Shoot me a message if you have any problems, although the only person who will probably have any issues will be me ;)
