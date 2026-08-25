# Registro de Propriedade Intelectual — IFMS

## Deploy no servidor (systemd de usuário)

Não use `sudo`. O Git envia os `.sh` sem bit de execução.

```bash
ssh -o ServerAliveInterval=60 -o ServerAliveCountMax=3 rpi@ifms.pro.br -p 2051

# a pasta ~/project já existe e não está vazia
rm -rf ~/project
git clone https://github.com/gt-computacao/RTI.git ~/project
cd ~/project

chmod +x scripts/setup-linux.sh scripts/start.sh

cp .env.example .env
nano .env
```

No `.env` do servidor edite informações como essas:

```
APP_PORT=2063
APP_BASE_URL=http://ifms.pro.br:2063
GOOGLE_REDIRECT_URI=http://ifms.pro.br:2063/auth/google/callback

POSTGRES_HOST=localhost
DATABASE_URL=postgresql+psycopg2://rpi_user:Rpi_password@localhost:5432/rpi_db

MAIL_HOST=localhost
MAIL_PORT=25
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_USE_TLS=false
```

Valores com espaço precisam de aspas. A mesma `GOOGLE_REDIRECT_URI` deve estar no Google Cloud (OAuth).

```bash
./scripts/setup-linux.sh

# o unit executa ~/project/start.sh (não ~/start.sh)
cp scripts/start.sh ~/project/start.sh
chmod +x ~/project/start.sh

systemctl --user restart rpi.service
systemctl --user status rpi.service
```

Conferir permissões (`x` no dono):

```bash
ls -l scripts/setup-linux.sh scripts/start.sh ~/project/start.sh
journalctl --user -u rpi.service -n 30
```

Deve aparecer `Uvicorn running on http://0.0.0.0:2063`.

URL: http://ifms.pro.br:2063/

```bash
systemctl --user start rpi.service
systemctl --user restart rpi.service
systemctl --user stop rpi.service
journalctl --user -u rpi.service -f
```
