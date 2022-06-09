### Using tg-archive as Docker container

In examples below we assume that:
- all files created will be owned by current user, that is why we have `--user="$(id -u):$(id -g)"` in Docker commands
- code is in folder `/home/user/tg-archive`
- main all sites folder is `/home/user/tg-archive/sites`
  This folder will keep all sites in sub-folders, with their DBs, configurations.
- example site created below will be named `test`
- build data will go into folder: `/var/www/public/test`

#### Build
1. Get source code and put it into: `/home/user/tg-archive`
2. In terminal `cd` to folder `/home/user/tg-archive`
3. Build `tg-archive` image: 
```bash
docker-compose build
```

#### Create new site
1. Make sure folder `/home/user/sites` exists
2. Create default site based on templates
```bash
 docker run --rm --user="$(id -u):$(id -g)" -v /home/user/sites:/sites tg-archive --new --path=/sites/test
```
3. Edit new site configuration, specially set `api_id`, `api_hash` and `group` parameters in file `config.yaml`


#### Create session file
Skip this step if file `session.session` you already created before.
Executing below will result in asking you about phone number and code sent you by Telegram
```bash
docker run --rm -it --user="$(id -u):$(id -g)" -v /home/user/sites:/sites tg-archive --config=/sites/test/config.yaml --session=/sites/session.session
```

#### Download site data
```bash
docker run --rm --user="$(id -u):$(id -g)" -v /home/user/sites:/sites tg-archive --config=/sites/test/config.yaml --session=/sites/session.session --sync
```

#### Build static site (publish)
```bash
docker run --rm --user="$(id -u):$(id -g)" -v /home/user/sites:/sites -v /var/www/public/test:/sites/test/site tg-archive --config=/sites/test/config.yaml --session=/sites/session.session --build
```
