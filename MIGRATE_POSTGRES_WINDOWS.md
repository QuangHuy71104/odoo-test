# Huong dan migrate PostgreSQL/Odoo sang may khac

File nay da duoc chinh theo may hien tai:

- Repo hien tai: `D:\University\knowledgeManagementSystem\odoo-test`
- PostgreSQL hien tai: `D:\University\knowledgeManagementSystem\Postgres`
- PostgreSQL data dir: `D:\University\knowledgeManagementSystem\Postgres\data`
- Database Odoo dang co: `TripleHandT`
- PostgreSQL user/password Odoo: `odoo` / `odoo`
- GitHub source: `https://github.com/Bodu-glitch/odoo-test.git`, branch `my-work`

## Buoc 1 - Export DB tren may hien tai

Chay tu thu muc PostgreSQL:

```powershell
cd D:\University\knowledgeManagementSystem\Postgres
$env:PGPASSWORD = 'odoo'
.\bin\pg_dump.exe -U odoo -h localhost -p 5432 TripleHandT -F c --no-acl --no-owner -f D:\University\knowledgeManagementSystem\odoo-test\TripleHandT_backup.dump
```

`-F c` tao dump custom format, nen restore bang `pg_restore`.

## Buoc 2 - Copy sang may moi

Copy cac thu sau:

- `TripleHandT_backup.dump`
- Source code, nen clone tu GitHub branch `my-work`
- Filestore neu co attachment: `D:\University\knowledgeManagementSystem\odoo-test\data\filestore\TripleHandT\`

Luu y: database chi luu metadata attachment. File that su cua attachment nam trong filestore. Tren may hien tai DB dang co attachment trong filestore, nen neu muon giu anh/file dinh kem thi phai copy filestore.

## Buoc 3 - Cai source tren may moi

```powershell
git clone https://github.com/Bodu-glitch/odoo-test.git
cd odoo-test
git checkout my-work
pip install -r requirements-win.txt
```

Neu dung PostgreSQL portable/local giong may nay, dat PostgreSQL o mot thu muc rieng, vi du:

```powershell
D:\University\knowledgeManagementSystem\Postgres
```

Start PostgreSQL:

```powershell
cd D:\University\knowledgeManagementSystem\Postgres
.\bin\pg_ctl.exe -D .\data -l .\data\log\postgresql.log start
```

Kiem tra PostgreSQL:

```powershell
.\bin\pg_isready.exe -h localhost -p 5432
```

## Buoc 4 - Tao user va database tren may moi

Chay bang superuser `postgres`:

```powershell
cd D:\University\knowledgeManagementSystem\Postgres
.\bin\psql.exe -U postgres -d postgres -c "CREATE USER odoo WITH PASSWORD 'odoo';"
.\bin\psql.exe -U postgres -d postgres -c "CREATE DATABASE ""TripleHandT"" OWNER odoo;"
.\bin\psql.exe -U postgres -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE ""TripleHandT"" TO odoo;"
```

Neu user/database da ton tai, co the bo qua lenh bi bao `already exists`.

## Buoc 5 - Restore DB

```powershell
cd D:\University\knowledgeManagementSystem\Postgres
$env:PGPASSWORD = 'odoo'
.\bin\pg_restore.exe -U odoo -h localhost -p 5432 -d TripleHandT -v D:\University\knowledgeManagementSystem\odoo-test\TripleHandT_backup.dump
```

Neu may moi dung PostgreSQL version khac, dump da co `--no-acl --no-owner` de giam loi permission.

## Buoc 6 - Tao/copy `odoo.conf`

`odoo.conf` bi gitignore, nen may moi can tao lai file nay o root repo `odoo-test`.

Mau theo may hien tai:

```ini
[options]
addons_path = D:\University\knowledgeManagementSystem\odoo-test\addons
data_dir = D:\University\knowledgeManagementSystem\odoo-test\data
admin_passwd = admin123
db_host = localhost
db_port = 5432
db_user = odoo
db_password = odoo
db_name = TripleHandT
http_port = 8069
logfile = D:\University\knowledgeManagementSystem\odoo-test\odoo.log
log_level = info
```

Neu repo/PostgreSQL nam o duong dan khac tren may moi, sua cac dong `addons_path`, `data_dir`, va `logfile` theo duong dan moi.

## Buoc 7 - Copy filestore

Neu may hien tai co thu muc:

```text
D:\University\knowledgeManagementSystem\odoo-test\data\filestore\TripleHandT\
```

copy sang may moi vao dung thu muc `data_dir\filestore\TripleHandT\`.

## Buoc 8 - Chay Odoo

```powershell
cd D:\University\knowledgeManagementSystem\odoo-test
.\venv\Scripts\Activate.ps1
python odoo-bin -c odoo.conf
```

Mo trinh duyet:

```text
http://localhost:8069
```
