import sys

packages = [
    ("flask", "Flask"),
    ("flask_cors", "Flask-CORS"),
    ("dotenv", "python-dotenv"),
    ("sqlalchemy", "SQLAlchemy"),
    ("requests", "requests"),
    ("PIL", "Pillow (PIL)"),
    ("numpy", "numpy"),
    ("torch", "PyTorch (torch)"),
    ("torchvision", "torchvision"),
    ("cv2", "OpenCV (cv2)")
]

failed = False
print(f"Testing packages on Python {sys.version}...")

for module_name, display_name in packages:
    try:
        __import__(module_name)
        print(f"[OK] {display_name} imported successfully.")
    except ImportError as e:
        print(f"[FAIL] {display_name} could not be imported. Error: {e}")
        failed = True

if failed:
    sys.exit(1)
else:
    print("All backend dependencies are verified and import successfully!")
    sys.exit(0)
