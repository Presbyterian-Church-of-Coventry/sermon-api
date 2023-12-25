# Python for PCC

If you would like to run the uploading scripts manually, you can clone this repo, `cd` into the directory, and

`pip3 install -r requirements.txt`

Generate an API key with

`python3 main.py -key`

Then run the API with

`python3 main.py -a`

You can find an example of a frontend for the API we actually use in [Upload.vue](Upload.vue). I'd recommend pulling the Docker image from coventrypca/sermonupload:latest, or you could clone this repository and build it yourself with `docker build .`

However, one thing not currently implemented for variable supply is Google's refresh token, which is a pain to get ahold of. As I'm unaware of the IP this script is being run from, you can only authenticate it on your local machine. So until I can figure out a better solution, you need to supply at least the client ID and secret for Google, then run the Youtube upload function and follow the link it gets you. Follow the steps there and the script should automatically create an oauth2.json file in your `data` directory. You can then build the Docker image for your own use with this important file in place with `docker build .`. Or simply bind `data/oauth2.json` to somewhere on your local file system and fill the file in that way.

If you would like to run the API on bare metal, rename `.env_example` to `.env` and fill the variables in there, then run `python3 main.py -a`.

Use the [Docker Compose File](docker-compose.yml) as a guide for filling in all the nessecary environment variables. See the chart below for their meanings:

| Env Variable     | Comment                                                                                                                              |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| SA_API_KEY       | Your SermonAudio API Key. You can find it by signing in and going [here](https://www.sermonaudio.com/secure/members_stats.asp)       |
| S3_ACCESS_KEY    | Get your access token for your S3 storage if you have it. If not, don't supply it and this part won't run                            |
| S3_SECRET        | Same as above, but use your secret token here. You could also use Docker secrets as this is sensitive                                |
| YT_CLIENT_ID     | The client ID for an OAUTH application you can create [here](https://console.cloud.google.com/projectcreate) with Youtube API access |
| YT_CLIENT_SECRET | The same thing, but supply the secret token as well                                                                                  |
| CHANNEL_ID       | Supply the _ID_ of the channel you would like to scrape for latest video to scrub through on the web interface.                      |
| REPO_URL         | Put the HTTPS URL for your Git repository here, where a markdown file will be made to upload                                         |
| GIT_USER         | Put your Git username here                                                                                                           |
| GIT_PASS         | And your Git password here. No special characters or things will break.                                                              |

Enjoy! If anyone else ever tries to use it it'll need to be customized a great deal, but some basic functionality should be implemented. Shoot me a message if you have any problems, although the only person who will probably have any issues will be me ;)

Todo:

- [ ] Fix creation of oauth2.json and find simpler way to get refresh token. Maybe automatically?

Pie in the sky:

- [ ] Automate completely by subtitle scanning for "Please be seated" and "Amen."
