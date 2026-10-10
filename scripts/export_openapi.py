"""Export actual app schemas; enrich transparent Gateway routes with upstream models."""
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
env = dict(os.environ, USE_SQLITE='true')
# Separate interpreters because the existing apps use same top-level module names.
def schema(service):
    output = subprocess.check_output([sys.executable, '-c', 'import json; from main import app; print(json.dumps(app.openapi()))'], cwd=root/service, env=env)
    return json.loads(output)

gateway = schema('gateway')
upstream = schema('user_management')
gateway['components'].setdefault('schemas', {}).update(upstream['components']['schemas'])
gateway['components'].setdefault('securitySchemes', {})['BearerAuth'] = {'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'JWT'}
for path, methods in upstream['paths'].items():
    if path.startswith('/internal') or path in ('/', '/health'):
        continue
    if path in ('/register', '/login', '/refresh'):
        public_paths = ['/api/v1/auth' + path]
    elif path.startswith('/me'):
        public_paths = ['/api/v1/users' + path]
        if path == '/me':
            public_paths.append('/api/v1/auth/me')
    else:
        public_paths = ['/api/v1' + path]
    for public in public_paths:
        assert public in gateway['paths'], f'Missing Gateway route: {public}'
        operations = json.loads(json.dumps(methods))
        for method, operation in operations.items():
            assert method in gateway['paths'][public], f'Missing Gateway method: {method} {public}'
            operation['operationId'] = public.replace('/', '_') + '_' + method
            params = operation.get('parameters', [])
            operation['parameters'] = [p for p in params if p.get('name') != 'authorization']
            if path not in ('/register', '/login', '/refresh', '/testimonials'):
                operation['security'] = [{'BearerAuth': []}]
            if path.startswith('/admin'):
                operation['description'] = 'Requires PostgreSQL SYSTEM_ADMIN role.'
        gateway['paths'][public] = operations
gateway['servers'] = [{'url': 'https://gateway-production-3c64.up.railway.app'}]
(root/'GATEWAY_OPENAPI.json').write_text(json.dumps(gateway, indent=2) + '\n')
print('Exported GATEWAY_OPENAPI.json')
