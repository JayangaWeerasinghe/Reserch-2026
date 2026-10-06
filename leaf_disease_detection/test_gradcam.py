import urllib.request
import json
import time
import os
from PIL import Image
from io import BytesIO

def build_multipart(file_bytes, filename, form_data):
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = bytearray()
    for key, val in form_data.items():
        body.extend(f"--{boundary}\r\n".encode('utf-8'))
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode('utf-8'))
        body.extend(f"{val}\r\n".encode('utf-8'))
    
    body.extend(f"--{boundary}\r\n".encode('utf-8'))
    body.extend(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode('utf-8'))
    body.extend(b'Content-Type: image/jpeg\r\n\r\n')
    body.extend(file_bytes)
    body.extend(b'\r\n')
    body.extend(f"--{boundary}--\r\n".encode('utf-8'))
    return bytes(body), f'multipart/form-data; boundary={boundary}'

print("--- Testing new API Analyze with Grad-CAM ---")

# Mock image (model will evaluate it, possibly producing a TOP_K or LOW_CONFIDENCE prediction)
# If it produces OOD, this test won't verify the queue logic well. 
img = Image.open('d:/paka/PaddyGuard_FullStack/PaddyGuard_FullStack/backend/data/uploads/PG-1C574DC5FE25.JPG')
img_bytes = BytesIO()
img.save(img_bytes, format='JPEG')

form_data = {
    "city": "Colombo",
    "field_area_acres": "1.0",
    "affected_field_percentage": "10.0"
}

data, content_type = build_multipart(img_bytes.getvalue(), "test_leaf_gradcam.jpg", form_data)

req = urllib.request.Request('http://localhost:8000/api/analyze', data=data, headers={'Content-Type': content_type})
res = urllib.request.urlopen(req)
res_data = json.loads(res.read())

case_id = res_data.get('case_id')
print("Analyzed Case ID:", case_id)
print("Prediction Status:", res_data['prediction']['status'])
print("Confidence:", res_data['prediction']['confidence'])

if not case_id:
    print("OOD, cannot test queue.")
    exit(0)

# Check queue
req_queue = urllib.request.Request('http://localhost:8000/api/expert/review-queue')
res_queue = urllib.request.urlopen(req_queue)
queue = json.loads(res_queue.read())

case_in_q = next((c for c in queue if c['case_id'] == case_id), None)

if case_in_q:
    print("Case entered queue.")
    print("Original Image URL:", case_in_q.get('original_image_url'))
    print("Grad-CAM Image URL:", case_in_q.get('gradcam_image_url'))
    assert case_in_q.get('original_image_url'), "Must have original image url"
    assert case_in_q.get('gradcam_image_url'), "Must have gradcam url"
else:
    print("Case did not enter queue (confidence too high).")

print("Checking disk files...")
uploads_dir = 'd:/paka/PaddyGuard_FullStack/PaddyGuard_FullStack/backend/data/uploads'
gradcam_dir = 'd:/paka/PaddyGuard_FullStack/PaddyGuard_FullStack/backend/data/gradcam'

# Find the files by case id
upload_files = [f for f in os.listdir(uploads_dir) if case_id in f]
gradcam_files = [f for f in os.listdir(gradcam_dir) if case_id in f]

print("Original image saved:", len(upload_files) > 0)
print("Grad-CAM image saved:", len(gradcam_files) > 0)

assert len(upload_files) > 0, "Original image missing on disk"
assert len(gradcam_files) > 0, "Grad-CAM image missing on disk"

print("All validations passed.")
