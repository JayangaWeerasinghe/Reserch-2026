"""
PaddyGuard Runtime Verification Script
Runs all checks and prints PASS/FAIL/BLOCKED/WARNING.
IMPORTANT: Never prints secret values.
"""
import os, sys, time, json, tempfile, shutil
from pathlib import Path

# Load .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

results = []

def report(check, status, evidence):
    results.append((check, status, evidence))
    tag = {"PASS": "[+]", "FAIL": "[X]", "BLOCKED": "[~]", "WARNING": "[!]"}.get(status, "?")
    print(f"[{status}] {tag} {check} -- {evidence}")

# ──────────────────────────────────────────────
# 1. ENV VARIABLES
# ──────────────────────────────────────────────
required_vars = [
    'MONGODB_URI','CLOUDINARY_CLOUD_NAME','CLOUDINARY_API_KEY','CLOUDINARY_API_SECRET',
    'SECRET_KEY','SUPER_ADMIN_USERNAME','SUPER_ADMIN_PASSWORD','MODEL_PATH',
    'TEST_DATASET_PATH','FRONTEND_ORIGIN'
]
missing = [v for v in required_vars if not os.environ.get(v, '').strip()]
if missing:
    report("backend env loaded", "FAIL", f"Missing: {', '.join(missing)}")
    print("CRITICAL: Cannot continue without required env vars.")
    sys.exit(1)
else:
    report("backend env loaded", "PASS", "All 10 required variables present (values hidden)")

# ──────────────────────────────────────────────
# 2. MONGODB CONNECTION
# ──────────────────────────────────────────────
try:
    from pymongo import MongoClient
    from urllib.parse import urlparse
    uri = os.environ['MONGODB_URI']
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    client.admin.command('ismaster')
    # Extract safe db name
    parsed = urlparse(uri)
    db_name = parsed.path.strip('/') or 'paddyguard'
    db = client[db_name]
    report("MongoDB connection", "PASS", f"Connected to database: {db_name}")
    
    # Check collections
    existing_cols = db.list_collection_names()
    expected_cols = [
        'prediction_cases','expert_users','active_learning_batches',
        'active_learning_batch_samples','candidate_models','training_jobs','deployed_models'
    ]
    found_cols = [c for c in expected_cols if c in existing_cols]
    missing_cols = [c for c in expected_cols if c not in existing_cols]
    col_evidence = f"Found: {found_cols}"
    if missing_cols:
        col_evidence += f" | Empty/missing: {missing_cols}"
    report("MongoDB collections", "PASS", col_evidence)
    
    # Sample record counts (read-only)
    counts = {}
    for col in found_cols:
        try:
            counts[col] = db[col].count_documents({})
        except:
            counts[col] = "error"
    count_str = ", ".join(f"{k}={v}" for k,v in counts.items())
    print(f"  [INFO] Collection record counts: {count_str}")
    MONGO_OK = True
    MONGO_CLIENT = client
    MONGO_DB_NAME = db_name
    
except Exception as e:
    report("MongoDB connection", "FAIL", f"Error: {type(e).__name__}: {str(e)[:120]}")
    report("MongoDB collections", "BLOCKED", "MongoDB connection failed")
    MONGO_OK = False

# ──────────────────────────────────────────────
# 3. CLOUDINARY
# ──────────────────────────────────────────────
try:
    import cloudinary
    import cloudinary.uploader
    cloudinary.config(
        cloud_name=os.environ['CLOUDINARY_CLOUD_NAME'],
        api_key=os.environ['CLOUDINARY_API_KEY'],
        api_secret=os.environ['CLOUDINARY_API_SECRET'],
        secure=True
    )
    # Create a tiny test image in temp
    import struct, zlib
    def tiny_png():
        def mk_chunk(name, data):
            c = zlib.crc32(name + data) & 0xffffffff
            return struct.pack('>I', len(data)) + name + data + struct.pack('>I', c)
        ihdr = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
        idat = zlib.compress(b'\x00\xff\xff\xff')
        return b'\x89PNG\r\n\x1a\n' + mk_chunk(b'IHDR', ihdr) + mk_chunk(b'IDAT', idat) + mk_chunk(b'IEND', b'')
    
    tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    tmp.write(tiny_png())
    tmp.close()
    
    upload_result = cloudinary.uploader.upload(
        tmp.name,
        folder="paddyguard/verify_test",
        public_id="verify_runtime_test",
        overwrite=True
    )
    os.unlink(tmp.name)
    
    secure_url = upload_result.get('secure_url', '')
    public_id  = upload_result.get('public_id', '')
    
    if secure_url.startswith('https://'):
        report("Cloudinary test upload", "PASS", f"secure_url returned (public_id={public_id})")
    else:
        report("Cloudinary test upload", "FAIL", "secure_url not returned or invalid")
    
    # Delete test asset
    del_result = cloudinary.uploader.destroy(public_id)
    if del_result.get('result') == 'ok':
        report("Cloudinary test cleanup", "PASS", f"Test asset deleted: {public_id}")
    else:
        report("Cloudinary test cleanup", "WARNING", f"Deletion result: {del_result}")
    
    CLOUDINARY_OK = True

except Exception as e:
    report("Cloudinary test upload", "FAIL", f"{type(e).__name__}: {str(e)[:120]}")
    report("Cloudinary test cleanup", "BLOCKED", "Upload failed")
    CLOUDINARY_OK = False

# ──────────────────────────────────────────────
# 4. MODEL LOADING
# ──────────────────────────────────────────────
try:
    import torch
    import torch.nn as nn
    from torchvision import models as tv_models
    
    model_path_rel = os.environ.get('MODEL_PATH', 'models/PaddyGuard_active_learning_round2.pth')
    # Path should be relative to backend dir
    backend_dir = Path(__file__).parent
    model_path = backend_dir / model_path_rel
    
    if not model_path.exists():
        report("Current model loading", "FAIL", f"File not found: {model_path_rel}")
    else:
        # Check no absolute Windows path dependency
        abs_path = str(model_path.resolve())
        if ":" in model_path_rel and model_path_rel[1] == ":":  # e.g. D:\...
            report("Current model loading", "FAIL", f"MODEL_PATH contains absolute Windows path: {model_path_rel}")
        else:
            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            checkpoint = torch.load(model_path, map_location=device, weights_only=False)
            
            # Build same EfficientNetB3 arch
            model = tv_models.efficientnet_b3(weights=None)
            num_ftrs = model.classifier[1].in_features
            model.classifier = nn.Sequential(
                nn.Dropout(p=0.3, inplace=True),
                nn.Linear(num_ftrs, 4)
            )
            
            # Load state dict
            state_dict = checkpoint.get('model_state_dict', checkpoint)
            model.load_state_dict(state_dict, strict=True)
            model.to(device)
            model.eval()
            
            out_features = model.classifier[1].out_features
            report("Current model loading", "PASS", 
                   f"EfficientNetB3 loaded | {out_features} classes | device={device} | path is relative ✓")
            MODEL_LOADED = True
            MODEL_OBJ = model
            DEVICE = device
except Exception as e:
    report("Current model loading", "FAIL", f"{type(e).__name__}: {str(e)[:150]}")
    MODEL_LOADED = False

# ──────────────────────────────────────────────
# 5. HEALTH ENDPOINT  (call the live server)
# ──────────────────────────────────────────────
import urllib.request, urllib.error
try:
    req = urllib.request.urlopen("http://localhost:8000/api/health", timeout=10)
    data = json.loads(req.read())
    status_ok = data.get('status') == 'ok'
    db_ok     = data.get('database') == 'connected'
    mdl_ok    = data.get('model_loaded') == True
    
    if status_ok and db_ok and mdl_ok:
        report("/api/health", "PASS", f"status=ok, database=connected, model_loaded=true")
    elif status_ok and mdl_ok:
        report("/api/health", "WARNING", f"status=ok, model_loaded=true, but database={data.get('database')}")
    else:
        report("/api/health", "FAIL", f"Response: {data}")
except urllib.error.URLError as e:
    report("/api/health", "BLOCKED", f"Server not reachable: {e.reason}")
except Exception as e:
    report("/api/health", "FAIL", f"{type(e).__name__}: {str(e)[:120]}")

# ──────────────────────────────────────────────
# 6. AUTHENTICATION
# ──────────────────────────────────────────────
import urllib.parse
AUTH_TOKEN = None

def do_request(url, method='GET', data=None, headers=None, token=None):
    req = urllib.request.Request(url, method=method)
    if data:
        req.add_header('Content-Type', 'application/json')
        req.data = json.dumps(data).encode()
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    if headers:
        for k,v in headers.items():
            req.add_header(k, v)
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return resp.getcode(), json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
        except:
            body = {}
        return e.code, body
    except Exception as ex:
        return None, str(ex)

try:
    username = os.environ['SUPER_ADMIN_USERNAME']
    password = os.environ['SUPER_ADMIN_PASSWORD']
    
    code, resp = do_request(
        "http://localhost:8000/api/auth/login",
        method='POST',
        data={"username": username, "password": password}
    )
    if code == 200 and resp.get('token'):
        AUTH_TOKEN = resp['token']
        report("Authentication", "PASS", "Login succeeded, token received (value hidden)")
    elif code == 200 and resp.get('access_token'):
        AUTH_TOKEN = resp['access_token']
        report("Authentication", "PASS", "Login succeeded, access_token received (value hidden)")
    else:
        report("Authentication", "FAIL", f"HTTP {code} — {str(resp)[:120]}")
except urllib.error.URLError as e:
    report("Authentication", "BLOCKED", f"Server not reachable: {getattr(e,'reason',str(e))}")
except Exception as e:
    report("Authentication", "FAIL", f"{type(e).__name__}: {str(e)[:120]}")

# Unauthorized access rejection
try:
    code, resp = do_request("http://localhost:8000/api/dashboard/stats", method='GET')
    if code in (401, 403):
        report("Unauthorized access rejection", "PASS", f"HTTP {code} returned with no token")
    elif code == 200:
        report("Unauthorized access rejection", "FAIL", "Protected endpoint returned 200 without token")
    else:
        report("Unauthorized access rejection", "WARNING", f"HTTP {code} — {str(resp)[:80]}")
except urllib.error.URLError as e:
    report("Unauthorized access rejection", "BLOCKED", f"Server not reachable")
except Exception as e:
    report("Unauthorized access rejection", "FAIL", f"{type(e).__name__}: {str(e)[:80]}")

# ──────────────────────────────────────────────
# 7. READ-ONLY API CHECKS
# ──────────────────────────────────────────────
ENDPOINTS = [
    ("Dashboard",            "GET", "/api/expert/dashboard-stats"),
    ("Expert review API",    "GET", "/api/expert/review-queue"),
    ("Fine-tune readiness",  "GET", "/api/expert/fine-tune/readiness"),
    ("Candidate API",        "GET", "/api/expert/model-candidates"),
    ("History",              "GET", "/api/cases"),
    ("Deployed model",       "GET", "/api/expert/deployed-model"),
]

for label, method, path in ENDPOINTS:
    if not AUTH_TOKEN:
        report(label, "BLOCKED", "No auth token available")
        continue
    try:
        code, resp = do_request(f"http://localhost:8000{path}", method=method, token=AUTH_TOKEN)
        if code == 200:
            report(label, "PASS", f"HTTP 200 OK")
        elif code in (401, 403):
            report(label, "FAIL", f"HTTP {code} — token rejected")
        elif code == 404:
            report(label, "BLOCKED", f"HTTP 404 — endpoint may not exist at this path")
        else:
            report(label, "FAIL", f"HTTP {code} — {str(resp)[:100]}")
    except urllib.error.URLError as e:
        report(label, "BLOCKED", f"Server not reachable")
    except Exception as e:
        report(label, "FAIL", f"{type(e).__name__}: {str(e)[:80]}")

# ──────────────────────────────────────────────
# 8. PREDICTION / ANALYZE
# ──────────────────────────────────────────────
import urllib.request, urllib.parse
import io

def find_test_image():
    """Find a safe rice leaf image from test data."""
    backend_dir = Path(__file__).parent
    test_path = backend_dir / os.environ.get('TEST_DATASET_PATH', 'data/test_dataset')
    # Walk and find first .jpg or .png
    for ext in ['*.jpg','*.jpeg','*.png']:
        found = list(test_path.rglob(ext))
        if found:
            return found[0]
    return None

try:
    img_path = find_test_image()
    if not img_path:
        report("Prediction", "BLOCKED", "No test image found in TEST_DATASET_PATH")
        report("Cloudinary original image", "BLOCKED", "No test image")
        report("Cloudinary Grad-CAM", "BLOCKED", "No test image")
    else:
        # Copy to temp to avoid mutating test set
        tmp_img = Path(tempfile.mktemp(suffix=img_path.suffix))
        shutil.copy(img_path, tmp_img)

        # Build multipart form-data manually with required fields
        boundary = "PaddyVerifyBoundary123"
        with open(tmp_img, 'rb') as f:
            img_data = f.read()

        def field(name, value):
            return (
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"{name}\"\r\n\r\n"
                f"{value}\r\n"
            ).encode()

        body = (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"file\"; filename=\"verify_test{tmp_img.suffix}\"\r\n"
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode()
        body += img_data + b"\r\n"
        body += field("field_area_acres", "1.0")
        body += field("affected_field_percentage", "10")
        body += field("rice_variety", "Unknown")
        body += field("growth_stage", "Unknown")
        body += field("city", "Colombo")
        body += f"--{boundary}--\r\n".encode()

        tmp_img.unlink()

        req = urllib.request.Request("http://localhost:8000/api/analyze", data=body, method='POST')
        req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
        if AUTH_TOKEN:
            req.add_header('Authorization', f'Bearer {AUTH_TOKEN}')
        
        try:
            resp_obj = urllib.request.urlopen(req, timeout=60)
            code = resp_obj.getcode()
            resp = json.loads(resp_obj.read())
        except urllib.error.HTTPError as e:
            code = e.code
            try: resp = json.loads(e.read())
            except: resp = {}
        
        if code == 200:
            disease = resp.get('disease') or resp.get('prediction') or resp.get('predicted_class','?')
            conf    = resp.get('confidence') or resp.get('confidence_score','?')
            ood     = resp.get('is_ood') if 'is_ood' in resp else resp.get('ood_detected','N/A')
            orig_url = resp.get('image_url') or resp.get('original_image_url','')
            gcam_url = resp.get('gradcam_url') or resp.get('grad_cam_url','')
            
            report("Prediction", "PASS", f"disease={disease}, confidence={conf}, ood={ood}")
            
            if orig_url and orig_url.startswith('https://res.cloudinary.com'):
                report("Cloudinary original image", "PASS", "Absolute Cloudinary https URL returned")
            elif orig_url:
                report("Cloudinary original image", "FAIL", f"URL not Cloudinary: {orig_url[:80]}")
            else:
                report("Cloudinary original image", "FAIL", "No image URL in response")
            
            if gcam_url and gcam_url.startswith('https://res.cloudinary.com'):
                report("Cloudinary Grad-CAM", "PASS", "Absolute Cloudinary https Grad-CAM URL returned")
            elif gcam_url:
                report("Cloudinary Grad-CAM", "WARNING", f"Grad-CAM URL present but not Cloudinary: {gcam_url[:80]}")
            else:
                report("Cloudinary Grad-CAM", "WARNING", "No Grad-CAM URL in response (may be OOD result)")
        else:
            report("Prediction", "FAIL", f"HTTP {code} — {str(resp)[:120]}")
            report("Cloudinary original image", "BLOCKED", "Prediction failed")
            report("Cloudinary Grad-CAM", "BLOCKED", "Prediction failed")

except Exception as e:
    report("Prediction", "FAIL", f"{type(e).__name__}: {str(e)[:120]}")
    report("Cloudinary original image", "BLOCKED", "Exception during prediction")
    report("Cloudinary Grad-CAM", "BLOCKED", "Exception during prediction")

# ──────────────────────────────────────────────
# 9. CORS VERIFICATION
# ──────────────────────────────────────────────
frontend_origin = os.environ.get('FRONTEND_ORIGIN','').split(',')[0].strip()

def cors_check(origin):
    req = urllib.request.Request("http://localhost:8000/api/health", method='GET')
    req.add_header('Origin', origin)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        acao = resp.headers.get('Access-Control-Allow-Origin','')
        return True, acao
    except urllib.error.HTTPError as e:
        acao = e.headers.get('Access-Control-Allow-Origin','')
        return False, acao
    except Exception as ex:
        return False, str(ex)

try:
    ok, acao = cors_check(frontend_origin or 'http://localhost:5173')
    if acao and (acao == '*' or acao == (frontend_origin or 'http://localhost:5173')):
        report("CORS allowed origin", "PASS", f"Origin '{frontend_origin}' accepted — ACAO header present")
    elif ok:
        report("CORS allowed origin", "WARNING", f"Request succeeded but ACAO header was: '{acao}'")
    else:
        report("CORS allowed origin", "FAIL", f"Request blocked. ACAO={acao}")
except Exception as e:
    report("CORS allowed origin", "BLOCKED", str(e)[:80])

try:
    ok, acao = cors_check("https://evil-attacker.com")
    if not acao or acao == '':
        report("CORS unrelated origin blocked", "PASS", "Unrelated origin gets no ACAO header")
    elif acao == '*':
        report("CORS unrelated origin blocked", "FAIL", "Wildcard CORS — ALL origins allowed!")
    else:
        report("CORS unrelated origin blocked", "WARNING", f"Unrelated origin got ACAO={acao}")
except Exception as e:
    report("CORS unrelated origin blocked", "BLOCKED", str(e)[:80])

# ──────────────────────────────────────────────
# PRINT FINAL SUMMARY TABLE
# ──────────────────────────────────────────────
print("\n" + "="*70)
print("FINAL VERIFICATION REPORT")
print("="*70)
print(f"{'Check':<40} {'Status':<10} Evidence")
print("-"*70)
for check, status, evidence in results:
    print(f"{check:<40} {status:<10} {evidence}")
print("="*70)

failed  = [r for r in results if r[1] == 'FAIL']
blocked = [r for r in results if r[1] == 'BLOCKED']

if failed or blocked:
    print("\nNOT YET PRODUCTION READY")
    if failed:
        print(f"  FAIL items: {[r[0] for r in failed]}")
    if blocked:
        print(f"  BLOCKED items: {[r[0] for r in blocked]}")
else:
    print("\nPRODUCTION READY")
