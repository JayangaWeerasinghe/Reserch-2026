import urllib.request
import json
import time
from pymongo import MongoClient

API_QUEUE = 'http://localhost:8000/api/expert/review-queue'

def get_auth_token():
    try:
        login_url = "http://localhost:8000/api/auth/login"
        data = json.dumps({"username": "superadmin", "password": "PaddyGuard@2026"}).encode('utf-8')
        req = urllib.request.Request(login_url, method="POST", data=data, headers={'Content-Type': 'application/json'})
        res = urllib.request.urlopen(req)
        resp_data = json.loads(res.read())
        return resp_data.get("token")
    except Exception as e:
        print("Login failed, proceeding without token:", e)
        return None

def insert_case(case_id, conf, ood=False):
    client = MongoClient("mongodb://localhost:27017")
    db = client["paddyguard"]
    status = "OOD" if ood else "KNOWN"
    needs_review = True if conf < 0.50 and not ood else False
    reason = 'LOW_CONFIDENCE' if needs_review else None
    
    db["prediction_cases"].insert_one({
        "case_id": case_id,
        "image_name": 'test.jpg',
        "predicted_disease": 'Brown_Spot',
        "confidence": conf,
        "status": status,
        "needs_expert_review": needs_review,
        "review_status": 'pending',
        "review_reason": reason,
        "consumed_by_job_id": None,
        "approved_for_training": False
    })
    client.close()

def clear_test_cases():
    client = MongoClient("mongodb://localhost:27017")
    db = client["paddyguard"]
    db["prediction_cases"].delete_many({"case_id": {"$regex": "^PG-TEST-HYBRID-"}})
    client.close()

def get_queue(token=None):
    time.sleep(0.5) # allow server to reload/settle
    try:
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        req = urllib.request.Request(API_QUEUE, headers=headers)
        res = urllib.request.urlopen(req)
        return json.loads(res.read())
    except Exception as e:
        print("API Error:", e)
        return []

def run_tests():
    print("--- Cleaning old test cases ---")
    clear_test_cases()
    
    token = get_auth_token()
    print("Fetched auth token:", token is not None)
    
    # 1. OOD case
    print("\n--- Test 1: OOD Case ---")
    insert_case('PG-TEST-HYBRID-OOD', 0.20, ood=True)
    q = get_queue(token)
    ood_in_q = any(c['case_id'] == 'PG-TEST-HYBRID-OOD' for c in q)
    print("OOD in queue?", ood_in_q)
    assert not ood_in_q, "OOD case should not enter queue"
    
    # 2. Absolute threshold < 0.50
    print("\n--- Test 2: Absolute Threshold < 0.50 ---")
    insert_case('PG-TEST-HYBRID-ABS', 0.45, ood=False)
    q = get_queue(token)
    abs_case = next((c for c in q if c['case_id'] == 'PG-TEST-HYBRID-ABS'), None)
    print("Absolute < 0.50 case in queue?", abs_case is not None)
    assert abs_case is not None, "Absolute < 0.50 case must enter queue"
    print("Reason:", abs_case['review_reason'])
    assert abs_case['review_reason'] == 'LOW_CONFIDENCE', "Reason must be LOW_CONFIDENCE"
    
    # 3. Top-K Uncertainty (6 eligible cases > 0.50)
    print("\n--- Test 3: Top-K Uncertainty (6 cases > 0.50) ---")
    confs = [0.99, 0.90, 0.85, 0.80, 0.75, 0.60]
    for i, c in enumerate(confs):
        insert_case(f'PG-TEST-HYBRID-TOPK-{i}', c, ood=False)
    
    q = get_queue(token)
    topk_cases = [c for c in q if c['case_id'].startswith('PG-TEST-HYBRID-TOPK')]
    print("Total Top-K cases in queue:", len(topk_cases))
    assert len(topk_cases) == 5, "Must strictly have 5 Top-K cases"
    
    # Verify lowest 5 are present
    in_q_confs = [c['confidence'] for c in topk_cases]
    print("Confidences in queue:", in_q_confs)
    assert 0.99 not in in_q_confs, "Highest confidence (0.99) must be excluded"
    
    # 4. Dynamic Top-K replacement
    print("\n--- Test 4: Dynamic Top-K Replacement ---")
    print("Inserting new case with conf 0.65")
    insert_case('PG-TEST-HYBRID-NEW-LOWER', 0.65, ood=False)
    
    q = get_queue(token)
    topk_cases_new = [c for c in q if c['case_id'].startswith('PG-TEST-HYBRID-TOPK') or c['case_id'] == 'PG-TEST-HYBRID-NEW-LOWER']
    print("Total Top-K cases in queue after insertion:", len(topk_cases_new))
    assert len(topk_cases_new) == 5, "Must still strictly have 5 Top-K cases"
    
    in_q_confs_new = [c['confidence'] for c in topk_cases_new]
    print("New Confidences in queue:", in_q_confs_new)
    assert 0.65 in in_q_confs_new, "New lower confidence case (0.65) must be present"
    assert 0.90 not in in_q_confs_new, "Previous highest confidence (0.90) must now be excluded"
    
    # 5. Verification persistence
    print("\n--- Test 5: Verification Persistence ---")
    verify_url = f"http://localhost:8000/api/expert/review-queue/PG-TEST-HYBRID-NEW-LOWER/verify"
    
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
        
    req = urllib.request.Request(
        verify_url, 
        method="PATCH", 
        data=json.dumps({"expert_label": "Healthy"}).encode('utf-8'), 
        headers=headers
    )
    try:
        res = urllib.request.urlopen(req)
        print("Verification response status:", res.status)
    except Exception as e:
        print("Verification failed:", e)
        
    q = get_queue(token)
    verified_in_q = any(c['case_id'] == 'PG-TEST-HYBRID-NEW-LOWER' for c in q)
    print("Verified Top-K case still in queue?", verified_in_q)
    assert not verified_in_q, "Verified case must disappear from queue"
    
    # Verify in History API
    req_history = urllib.request.Request('http://localhost:8000/api/cases')
    res_history = urllib.request.urlopen(req_history)
    history = json.loads(res_history.read())
    history_case = next((c for c in history if c['case_id'] == 'PG-TEST-HYBRID-NEW-LOWER'), None)
    
    print("History status of verified case:", history_case['review_status'])
    assert history_case['review_status'] == 'verified', "Must be marked verified in history"
    print("History needs_expert_review of verified case:", history_case['needs_expert_review'])
    assert history_case['needs_expert_review'] == True, "needs_expert_review must be permanently True"
    print("History review_reason of verified case:", history_case['review_reason'])
    assert history_case['review_reason'] == 'TOP_K_UNCERTAINTY', "Reason must be permanently TOP_K_UNCERTAINTY"

    print("\n--- All tests passed! Cleaning up... ---")
    clear_test_cases()
    print("Cleanup done.")

if __name__ == '__main__':
    run_tests()
