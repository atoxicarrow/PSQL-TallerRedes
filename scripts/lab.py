#!/usr/bin/env python3
"""Laboratorio reproducible con Podman. Solo usa la biblioteca estándar."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess as sp
import time

ROOT = Path(__file__).resolve().parents[1]
# .env es un archivo de valores, no se ejecuta como código.
cfg = {}
if (ROOT / '.env').exists():
    for line in (ROOT / '.env').read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            cfg[k.strip()] = v.strip()
def setting(k, default):
    return os.environ.get(k, cfg.get(k, default))
SERVER = setting('LAB_SERVER', 'pg_server')
CLIENT = setting('LAB_CLIENT', 'pg_client')
NETWORK = setting('LAB_NETWORK', 'taller_redes')
VOLUME = setting('LAB_VOLUME', 'taller_datos')
USER = setting('PGUSER', 'estudiante')
PASSWORD = setting('PGPASSWORD', 'clave_lab')
DB = setting('PGDATABASE', 'taller')
IMAGE = 'docker.io/library/postgres@sha256:ac838714b7d794185a866e5a6b479b954e7d8a070568aa0acac6fe07c3070bf5'
OUT = Path(setting('LAB_OUTPUT', str(ROOT)))

def run(args, check=True, **kw):
    return sp.run(args, text=True, stdout=sp.PIPE, stderr=sp.STDOUT, check=check, **kw)
def pod(*args, **kw):
    return run(['podman', *args], **kw)
def exists(kind, name):
    return pod(kind, 'exists', name, check=False).returncode == 0

def psql(sql=None, password=PASSWORD, stop=True):
    cmd = ['podman', 'exec', '-i', '-e', 'PGPASSWORD=' + password, CLIENT,
           'psql', '-X', '-w', '-h', SERVER, '-U', USER, '-d', DB,
           '-P', 'pager=off', '-a', '-v', 'ON_ERROR_STOP=' + ('1' if stop else '0')]
    return run(cmd, input=sql or '', check=False)

def setup():
    if not exists('network', NETWORK):
        print(pod('network', 'create', NETWORK).stdout)
    if not exists('volume', VOLUME):
        pod('volume', 'create', VOLUME)
    if not exists('container', SERVER):
        pod('run', '-d', '--name', SERVER, '--network', NETWORK,
            '-e', 'POSTGRES_USER=' + USER, '-e', 'POSTGRES_PASSWORD=' + PASSWORD,
            '-e', 'POSTGRES_DB=' + DB, '-v', VOLUME + ':/var/lib/postgresql/data', IMAGE)
    else:
        pod('start', SERVER)
    if not exists('container', CLIENT):
        print('Construyendo cliente con psql y tcpdump...')
        print(pod('build', '-t', 'localhost/taller-redes-cliente:16', '-f',
                  str(ROOT / 'Containerfile.cliente'), str(ROOT)).stdout)
        pod('run', '-d', '--name', CLIENT, '--network', NETWORK,
            '--cap-add=NET_RAW', '--init', 'localhost/taller-redes-cliente:16')
    else:
        pod('start', CLIENT)
    for _ in range(60):
        ready = pod('exec', SERVER, 'pg_isready', '-h', '127.0.0.1', '-U', USER, '-d', DB, check=False)
        if ready.returncode == 0:
            break
        time.sleep(1)
    else:
        raise RuntimeError('PostgreSQL no quedó listo en 60 segundos')
    result = psql((ROOT / 'sql/01_inicial.sql').read_text())
    print(result.stdout)
    if result.returncode:
        raise RuntimeError('Falló la conexión o la preparación SQL')
    print('Laboratorio listo. Las credenciales solo se aplican al inicializar un volumen nuevo.')


def capture(name, sql, password=PASSWORD, stop=True, expected=0):
    caps = OUT / 'capturas'
    evidence = OUT / 'evidencias'
    caps.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)
    target = '/tmp/taller_' + name + '.pcap'
    pidfile = target + '.pid'
    log = evidence / (name + '_tcpdump.txt')
    script = 'echo $$ > ' + shlex.quote(pidfile) + '; exec tcpdump --immediate-mode -i eth0 -p -nn -s 0 -U -w ' + shlex.quote(target) + " 'tcp port 5432'"
    with log.open('w') as handle:
        proc = sp.Popen(['podman', 'exec', '--user', 'root', CLIENT, 'sh', '-c', script], stdout=handle, stderr=handle)
        try:
            for _ in range(100):
                if 'listening on' in log.read_text():
                    break
                if proc.poll() is not None:
                    raise RuntimeError(log.read_text())
                time.sleep(.1)
            else:
                raise RuntimeError('No comenzó la captura')
            result = psql(sql, password=password, stop=stop)
            (evidence / (name + '_psql.txt')).write_text(result.stdout + '\nCódigo de salida: ' + str(result.returncode) + '\n')
            time.sleep(1.2)
        finally:
            pid = pod('exec', CLIENT, 'cat', pidfile, check=False).stdout.strip()
            if pid.isdigit():
                pod('exec', '--user', 'root', CLIENT, 'kill', '-INT', pid, check=False)
            try:
                proc.wait(timeout=10)
            except sp.TimeoutExpired:
                proc.terminate()
                proc.wait(timeout=5)
    pod('cp', CLIENT + ':' + target, str(caps / (name + '.pcap')))
    if (caps / (name + '.pcap')).stat().st_size <= 24:
        raise RuntimeError(name + ': captura vacía; revisar tcpdump')
    if result.returncode != expected:
        raise RuntimeError(f'{name}: salida {result.returncode}; se esperaba {expected}')
    print(name + ': OK (salida ' + str(result.returncode) + ')')


def environment():
    OUT.joinpath('evidencias').mkdir(parents=True, exist_ok=True)
    sections = []
    commands = [
        ['podman', '--version'], ['podman', 'ps', '--format', '{{.Names}} | {{.Status}} | {{.Image}}'],
        ['podman', 'network', 'inspect', NETWORK],
        ['podman', 'exec', CLIENT, 'psql', '--version'],
        ['podman', 'exec', CLIENT, 'tcpdump', '--version'],
        ['podman', 'exec', SERVER, 'psql', '-U', USER, '-d', DB, '-c',
         "SELECT version(); SHOW ssl; SHOW password_encryption; SELECT type,database,user_name,address,auth_method FROM pg_hba_file_rules WHERE type='host';"],
        ['tshark', '--version']]
    for cmd in commands:
        sections.append('$ ' + shlex.join(cmd) + '\n' + run(cmd, check=False).stdout)
    data = json.loads(pod('inspect', SERVER, CLIENT).stdout)
    summary = [{
        'name': c['Name'], 'image': c['ImageName'], 'command': c['Config']['Cmd'],
        'capabilities': c.get('EffectiveCaps'), 'networks': c['NetworkSettings']['Networks'],
        'mounts': [{'type': m['Type'], 'destination': m['Destination'], 'name': m.get('Name')} for m in c['Mounts']]}
        for c in data]
    (OUT / 'evidencias/configuracion.json').write_text(json.dumps(summary, indent=2))
    (OUT / 'evidencias/entorno.txt').write_text('\n\n'.join(sections))


def tests():
    environment()
    capture('01_sesion_completa', 'SELECT current_database(), current_user, inet_server_addr(), inet_server_port();\nSELECT * FROM equipos ORDER BY id;\n\\q\n')
    capture('02_crud', (ROOT / 'sql/02_crud.sql').read_text() + '\n\\q\n')
    capture('03_error_sql', (ROOT / 'sql/03_error.sql').read_text() + '\n\\q\n', stop=False)
    capture('04_auth_fallida', 'SELECT 1;\n', password='incorrecta_lab', expected=2)
    print('Pruebas completadas. La tabla equipos se conserva intacta.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['setup', 'test', 'stop'])
    action = parser.parse_args().action
    if action == 'setup': setup()
    elif action == 'test': tests()
    else:
        print(pod('stop', '--time', '2', CLIENT, SERVER).stdout)
