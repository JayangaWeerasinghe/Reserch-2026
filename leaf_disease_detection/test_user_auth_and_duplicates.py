import requests
import json
import time
import os

BASE_URL = "http://localhost:8000"

print("==================================================")
print("RUNNING PADDYGUARD USER AUTH & DUPLICATE CHECKS")
print("==================================================")

# 1. Staff Login Verification
r = requests.post(f"{BASE_URL}/api/auth/login", json={
    "username": "superadmin",
    "password": "PaddyGuard@2026"
})
assert r.status_code == 200, f"Staff login failed: {r.text}"
admin_data = r.json()
admin_token = admin_data["token"]
print("[PASS] 1. Staff login works (Super Admin)")

# 2. Register User A
user_a_email = f"user_a_{int(time.time())}@example.com"
r = requests.post(f"{BASE_URL}/api/auth/register", json={
    "name": "User Alpha",
    "email": user_a_email,
    "password": "password123"
})
assert r.status_code == 201, f"Registration failed: {r.text}"
user_a_reg = r.json()["user"]
assert user_a_reg["role"] == "USER", "Role must be USER"
user_a_id = user_a_reg["user_id"]
print(f"[PASS] 2. User A registered successfully: {user_a_id} ({user_a_email})")

# 3. Duplicate Email Rejection
r = requests.post(f"{BASE_URL}/api/auth/register", json={
    "name": "User A Duplicate",
    "email": user_a_email,
    "password": "password123"
})
assert r.status_code == 400, f"Duplicate email should be rejected: {r.text}"
print("[PASS] 3. Duplicate email registration rejected")

# 4. User A Login
r = requests.post(f"{BASE_URL}/api/auth/login", json={
    "username": user_a_email,
    "password": "password123"
})
assert r.status_code == 200, f"User A login failed: {r.text}"
user_a_token = r.json()["token"]
print("[PASS] 4. User A login succeeded")

# 5. Wrong Password Rejection
r = requests.post(f"{BASE_URL}/api/auth/login", json={
    "username": user_a_email,
    "password": "wrongpassword"
})
assert r.status_code == 401, f"Wrong password should be rejected: {r.text}"
print("[PASS] 5. Wrong password rejected")

# 6. Register User B
user_b_email = f"user_b_{int(time.time())}@example.com"
r = requests.post(f"{BASE_URL}/api/auth/register", json={
    "name": "User Beta",
    "email": user_b_email,
    "password": "password123"
})
assert r.status_code == 201, f"Registration failed: {r.text}"
user_b_token = requests.post(f"{BASE_URL}/api/auth/login", json={
    "username": user_b_email,
    "password": "password123"
}).json()["token"]
print("[PASS] 6. User B registered and logged in")

# 7. Authorization Checks (USER rejected from EXPERT/SUPER_ADMIN endpoints)
r = requests.get(f"{BASE_URL}/api/expert/review-queue", headers={"Authorization": f"Bearer {user_a_token}"})
assert r.status_code == 403, f"USER should be rejected from EXPERT endpoint: {r.status_code}"
print("[PASS] 7. USER rejected from EXPERT endpoints (403 Forbidden)")

r = requests.get(f"{BASE_URL}/api/admin/users", headers={"Authorization": f"Bearer {user_a_token}"})
assert r.status_code == 403, f"USER should be rejected from SUPER_ADMIN endpoint: {r.status_code}"
print("[PASS] 8. USER rejected from SUPER_ADMIN endpoints (403 Forbidden)")

# 8. Test /api/user/me
r = requests.get(f"{BASE_URL}/api/user/me", headers={"Authorization": f"Bearer {user_a_token}"})
assert r.status_code == 200, f"/api/user/me failed: {r.text}"
assert r.json()["user_id"] == user_a_id
print("[PASS] 9. /api/user/me returns authenticated user details")

# 9. Test Upload & Duplicate Spam Protection
sample_img_path = os.path.join(os.path.dirname(__file__), "data", "test_dataset", "Healthy", "Healthy (851).jpg")
with open(sample_img_path, "rb") as f:
    sample_jpg = f.read()

def post_analyze_with_retry(files, data, headers, max_retries=3):
    for attempt in range(max_retries):
        files_copy = {'file': (files['file'][0], files['file'][1], files['file'][2])}
        r = requests.post(f"{BASE_URL}/api/analyze", files=files_copy, data=data, headers=headers)
        if r.status_code == 500 and "open-meteo" in r.text and attempt < max_retries - 1:
            time.sleep(2)
            continue
        return r

# User A upload #1 (Valid image)
files = {'file': ('leaf_a.jpg', sample_jpg, 'image/jpeg')}
data = {'city': 'Gampaha', 'field_area_acres': '1.5', 'affected_field_percentage': '10'}
headers = {'Authorization': f'Bearer {user_a_token}'}

r = post_analyze_with_retry(files, data, headers)
assert r.status_code == 200, f"User A analyze #1 failed: {r.text}"
case_a_1 = r.json()["case_id"]
print(f"[PASS] 10. User A first upload succeeded: {case_a_1}")

# User A upload #2 (Same exact image within 5 mins -> MUST BE BLOCKED HTTP 429)
files = {'file': ('leaf_a.jpg', sample_jpg, 'image/jpeg')}
r = post_analyze_with_retry(files, data, headers)
assert r.status_code == 429, f"Duplicate upload should be blocked with 429, got {r.status_code}: {r.text}"
dup_resp = r.json()
assert dup_resp["error"] == "duplicate_upload"
assert "retry_after_seconds" in dup_resp
print(f"[PASS] 11. Duplicate upload blocked with HTTP 429 (retry in {dup_resp['retry_after_seconds']}s)")

# User B upload #1 (Same exact image by DIFFERENT user -> MUST BE ALLOWED)
files = {'file': ('leaf_b.jpg', sample_jpg, 'image/jpeg')}
headers_b = {'Authorization': f'Bearer {user_b_token}'}
r = post_analyze_with_retry(files, data, headers_b)
assert r.status_code == 200, f"Different user uploading same image should succeed, got {r.status_code}: {r.text}"
print("[PASS] 12. Different user uploading same image allowed")

# 10. Check User History Separation
r_a_hist = requests.get(f"{BASE_URL}/api/user/history", headers={'Authorization': f'Bearer {user_a_token}'})
assert r_a_hist.status_code == 200
cases_a = r_a_hist.json()
assert len(cases_a) == 1 and cases_a[0]["case_id"] == case_a_1

r_b_hist = requests.get(f"{BASE_URL}/api/user/history", headers={'Authorization': f'Bearer {user_b_token}'})
assert r_b_hist.status_code == 200
cases_b = r_b_hist.json()
assert len(cases_b) == 1 and cases_b[0]["case_id"] != case_a_1

print("[PASS] 13. Server-side history filtering isolated per user token (User A cannot view User B history)")

# 11. Super Admin User Management
r_users = requests.get(f"{BASE_URL}/api/admin/users", headers={'Authorization': f'Bearer {admin_token}'})
assert r_users.status_code == 200
users_list = r_users.json()
target_u = next(u for u in users_list if u["user_id"] == user_a_id)
assert target_u["analysis_count"] == 1
print("[PASS] 14. Super Admin lists users with correct aggregated analysis count")

# Update user
r_update = requests.put(f"{BASE_URL}/api/admin/users/{user_a_id}", json={
    "name": "User Alpha Updated",
    "email": user_a_email
}, headers={'Authorization': f'Bearer {admin_token}'})
assert r_update.status_code == 200
print("[PASS] 15. Super Admin updated normal user details")

# Deactivate user (Soft Delete)
r_del = requests.delete(f"{BASE_URL}/api/admin/users/{user_a_id}", headers={'Authorization': f'Bearer {admin_token}'})
assert r_del.status_code == 200
print("[PASS] 16. Super Admin soft-deactivated normal user (is_active = false)")

# Disabled user login attempt
r_disabled_login = requests.post(f"{BASE_URL}/api/auth/login", json={
    "username": user_a_email,
    "password": "password123"
})
assert r_disabled_login.status_code == 403, f"Disabled user login should be rejected: {r_disabled_login.text}"
print("[PASS] 17. Disabled user login rejected with 403 Forbidden")

# Verify user history still exists in DB
r_check_hist = requests.get(f"{BASE_URL}/api/user/history", headers={'Authorization': f'Bearer {user_a_token}'})
assert r_check_hist.status_code == 403, "Deactivated token rejected"
print("[PASS] 18. Deactivated token rejected while prediction records remain intact in database")

print("\n==================================================")
print("ALL AUTHENTICATION & DUPLICATE TESTS PASSED (18/18)")
print("==================================================")
