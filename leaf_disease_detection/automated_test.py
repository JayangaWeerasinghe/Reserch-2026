import os
import json
from io import BytesIO
import unittest
from unittest.mock import patch
from PIL import Image

import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.main import app
from app.database import SessionLocal
from app.models import PredictionCase

class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        app.testing = True

    def build_multipart(self, file_bytes, filename, form_data):
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

    @patch('app.api.analyze.model_service.predict')
    def test_end_to_end_uncertain_flow(self, mock_predict):
        print("\n--- Testing Isolated UNCERTAIN (Low Confidence) Flow ---")
        
        # 1. Mock low confidence prediction
        mock_predict.return_value = {
            "status": "UNCERTAIN",
            "prediction": "Brown_Spot",
            "confidence": 0.65,
            "energy_score": 5.5,
            "is_low_confidence": True,
            "needs_expert_review": True,
            "severity_percentage": None,
            "severity_method": None,
            "gradcam_base64": None,
            "class_probabilities": {}
        }
        
        form_data = {
            "city": "Colombo",
            "field_area_acres": "1.0",
            "affected_field_percentage": "10.0"
        }
        
        img = Image.new('RGB', (300, 300), color=(100, 150, 100))
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        
        data, content_type = self.build_multipart(img_bytes.getvalue(), "test_leaf.jpg", form_data)
        
        # POST /api/analyze
        response = self.client.post('/api/analyze', data=data, content_type=content_type)
        res_json = json.loads(response.data)
        
        self.assertEqual(res_json['prediction']['status'], 'UNCERTAIN')
        self.assertTrue(res_json['prediction']['needs_expert_review'])
        self.assertTrue(res_json['prediction']['is_low_confidence'])
        case_id = res_json.get('case_id')
        self.assertIsNotNone(case_id)
        
        print(f"UNCERTAIN Response verified. Case ID: {case_id}")
        
        # 2. Verify queue
        q_res = self.client.get('/api/expert/review-queue')
        queue = json.loads(q_res.data)
        in_queue = any(c['case_id'] == case_id for c in queue)
        self.assertTrue(in_queue)
        print("Case successfully appeared in review queue.")
        
        # 3. Verify the case
        v_res = self.client.patch(f'/api/expert/review-queue/{case_id}/verify', json={"expert_label": "Leaf_Blast"})
        self.assertEqual(v_res.status_code, 200)
        print("Case successfully verified by expert.")
        
        # 4. Verify queue count decreases
        q_res2 = self.client.get('/api/expert/review-queue')
        queue2 = json.loads(q_res2.data)
        in_queue2 = any(c['case_id'] == case_id for c in queue2)
        self.assertFalse(in_queue2)
        print("Case successfully removed from pending review queue.")
        
        # 5. Check dashboard stats
        d_res = self.client.get('/api/expert/dashboard-stats')
        stats = json.loads(d_res.data)
        print("Dashboard stats after verification:", stats)
        
        # 6. Verify image persistence
        import glob
        files = glob.glob(os.path.join(app.config['UPLOAD_FOLDER'], f"{case_id}*"))
        self.assertTrue(len(files) > 0)
        print(f"Original uploaded image successfully saved at: {files[0]}")
        
        # Cleanup DB record
        with app.app_context():
            session = SessionLocal()
            session.query(PredictionCase).filter_by(case_id=case_id).delete()
            session.commit()
            session.close()
        
        # Cleanup file
        for f in files:
            os.remove(f)

if __name__ == '__main__':
    unittest.main()
