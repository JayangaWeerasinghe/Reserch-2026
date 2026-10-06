import argparse
import json
import logging
import os
import shutil
import sys
import time
import requests
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import datasets, models, transforms
from pymongo import MongoClient

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CLASS_NAMES = ["Bacterial_Blight", "Brown_Spot", "Healthy", "Leaf_Blast"]
CLASS_TO_IDX = {name: idx for idx, name in enumerate(CLASS_NAMES)}

def update_job_status(mongodb_uri, job_id, status, error=None, log_tail=None, decision=None):
    try:
        db_name = "paddyguard"
        from urllib.parse import urlparse
        try:
            parsed = urlparse(mongodb_uri)
            if parsed.path and parsed.path.strip("/"):
                db_name = parsed.path.strip("/")
        except Exception:
            pass
            
        client = MongoClient(mongodb_uri)
        db = client[db_name]
        now = datetime.now(timezone.utc).isoformat()
        
        updates = {"status": status}
        if status == "TRAINING":
            updates["started_at"] = now
        if status in ["COMPLETED", "FAILED"]:
            updates["completed_at"] = now
        if error:
            updates["error_message"] = error
        if log_tail:
            updates["log_tail"] = log_tail
        if decision:
            updates["decision"] = decision
            
        db["training_jobs"].update_one({"job_id": job_id}, {"$set": updates})
        client.close()
    except Exception as e:
        logger.error(f"Failed to update job status in DB: {e}")

def update_job_metrics(mongodb_uri, job_id, updates_dict):
    try:
        db_name = "paddyguard"
        from urllib.parse import urlparse
        try:
            parsed = urlparse(mongodb_uri)
            if parsed.path and parsed.path.strip("/"):
                db_name = parsed.path.strip("/")
        except Exception:
            pass
            
        client = MongoClient(mongodb_uri)
        db = client[db_name]
        
        db["training_jobs"].update_one({"job_id": job_id}, {"$set": updates_dict})
        client.close()
    except Exception as e:
        logger.error(f"Failed to update job metrics in DB: {e}")

class FineTuneDataset(Dataset):
    def __init__(self, samples, img_dir, transform=None):
        self.samples = samples
        self.img_dir = img_dir
        self.transform = transform

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        sample = self.samples[idx]
        img_name = sample['image_name']
        label_str = sample['label']
        
        img_path = os.path.join(self.img_dir, img_name)
        image = Image.open(img_path).convert("RGB")
        
        if self.transform:
            image = self.transform(image)
            
        label = CLASS_TO_IDX[label_str]
        return image, label

def get_db_samples(mongodb_uri, job_id):
    db_name = "paddyguard"
    from urllib.parse import urlparse
    try:
        parsed = urlparse(mongodb_uri)
        if parsed.path and parsed.path.strip("/"):
            db_name = parsed.path.strip("/")
    except Exception:
        pass
        
    client = MongoClient(mongodb_uri)
    db = client[db_name]
    cursor = db["prediction_cases"].find({"consumed_by_job_id": job_id})
    
    samples = []
    for doc in cursor:
        samples.append({
            "image_name": doc.get("image_name"),
            "image_url": doc.get("image_url"),
            "label": doc.get("expert_validated_disease")
        })
    client.close()
    return samples

def calculate_metrics(y_true, y_pred):
    """Calculate accuracy and macro F1 using pure numpy"""
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    
    accuracy = np.mean(y_true == y_pred)
    
    # Macro F1
    classes = np.unique(np.concatenate((y_true, y_pred)))
    f1_scores = []
    for c in classes:
        tp = np.sum((y_true == c) & (y_pred == c))
        fp = np.sum((y_true != c) & (y_pred == c))
        fn = np.sum((y_true == c) & (y_pred != c))
        
        if tp + fp + fn == 0:
            f1 = 0.0
        else:
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            if precision + recall == 0:
                f1 = 0.0
            else:
                f1 = 2 * (precision * recall) / (precision + recall)
        f1_scores.append(f1)
        
    macro_f1 = np.mean(f1_scores) if f1_scores else 0.0
    return accuracy, macro_f1

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--mongodb-uri", required=True)
    parser.add_argument("--test-dir", required=True)
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--total-verified-samples", type=int, default=None)
    parser.add_argument("--ood-excluded-samples", type=int, default=None)
    args = parser.parse_args()

    job_id = args.job_id
    mongodb_uri = args.mongodb_uri
    epochs = args.epochs

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    job_started_at = datetime.now(timezone.utc)
    job_start_time = time.time()

    logger.info("=" * 40)
    logger.info("PADDYGUARD IN-APP PYTORCH FINE-TUNING")
    logger.info("=" * 40)
    logger.info(f"Job ID: {job_id}")
    logger.info(f"Started at: {job_started_at.isoformat()}")
    logger.info(f"Device: {device}")

    update_job_status(mongodb_uri, job_id, "PREPARING")

    temp_dir = None
    try:
        # 1. Load Data from DB
        logger.info("[DATA] Loading expert-verified samples...")
        samples = get_db_samples(mongodb_uri, job_id)
        if not samples:
            raise ValueError("No samples found for this job ID")

        update_job_metrics(mongodb_uri, job_id, {"source_sample_count": len(samples)})

        total_verified_samples = args.total_verified_samples if args.total_verified_samples is not None else len(samples)
        ood_excluded_samples = args.ood_excluded_samples if args.ood_excluded_samples is not None else 0
        logger.info(f"[DATA] Total verified samples: {total_verified_samples}")
        logger.info(f"[DATA] Training eligible samples: {len(samples)}")
        logger.info(f"[DATA] OOD excluded: {ood_excluded_samples}")

        # 2. Setup temporary workspace and download Cloudinary images
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        temp_dir = os.path.join(backend_dir, "data", f"temp_training_{job_id}")
        os.makedirs(temp_dir, exist_ok=True)
        
        for s in samples:
            img_name = s["image_name"]
            img_url = s.get("image_url")
            local_dest = os.path.join(temp_dir, img_name)
            
            downloaded = False
            if img_url:
                try:
                    logger.info(f"Downloading original training image from Cloudinary: {img_url}")
                    r_img = requests.get(img_url, timeout=20)
                    if r_img.status_code == 200:
                        with open(local_dest, "wb") as f_img:
                            f_img.write(r_img.content)
                        downloaded = True
                except Exception as e:
                    logger.error(f"Cloudinary download failed for {img_name}: {e}")
                    
            if not downloaded:
                # Fallback to local uploads directory (original backups)
                local_backup = os.path.join(backend_dir, "data", "uploads", img_name)
                if os.path.exists(local_backup):
                    logger.info(f"Copying local backup image {img_name} to training workspace")
                    shutil.copy2(local_backup, local_dest)
                else:
                    raise FileNotFoundError(f"Training image {img_name} not found on Cloudinary or locally")

        # 3. Setup transforms
        IMAGE_SIZE = 300
        train_transform = transforms.Compose([
            transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(15),
            transforms.ColorJitter(brightness=0.2, contrast=0.2),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
        
        val_transform = transforms.Compose([
            transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])

        train_dataset = FineTuneDataset(samples, temp_dir, train_transform)
        train_loader = DataLoader(train_dataset, batch_size=4, shuffle=True)
        logger.info("[DATA] Fine-tuning DataLoader ready")
        logger.info(f"[DATA] Batch size: {train_loader.batch_size}")
        logger.info(f"[DATA] Number of batches: {len(train_loader)}")

        if not os.path.exists(args.test_dir):
            raise FileNotFoundError(f"Test dataset not found at {args.test_dir}")

        logger.info("[EVAL] Loading held-out test dataset...")
        test_dataset = datasets.ImageFolder(args.test_dir, transform=val_transform)
        test_loader = DataLoader(test_dataset, batch_size=16, shuffle=False)
        logger.info(f"[EVAL] Test samples: {len(test_dataset)}")

        # 4. Load Model
        logger.info(f"Using device: {device}")

        model = models.efficientnet_b3(weights=None)
        in_features = model.classifier[1].in_features
        model.classifier = nn.Sequential(
            nn.Dropout(p=0.4),
            nn.Linear(in_features, len(CLASS_NAMES))
        )

        logger.info("[MODEL] Loading deployed checkpoint...")
        logger.info(f"[MODEL] Checkpoint: {os.path.basename(args.base_model)}")
        checkpoint = torch.load(args.base_model, map_location=device)
        if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
            state_dict = checkpoint["model_state_dict"]
        elif isinstance(checkpoint, dict) and "state_dict" in checkpoint:
            state_dict = checkpoint["state_dict"]
        else:
            state_dict = checkpoint

        model.load_state_dict(state_dict)
        model = model.to(device)
        logger.info("[MODEL] Model loaded successfully")

        # Evaluate baseline (this is the authoritative "current" accuracy/F1 used for the promotion decision)
        update_job_status(mongodb_uri, job_id, "EVALUATING", log_tail="Evaluating baseline model...")
        model.eval()
        all_preds = []
        all_labels = []
        with torch.no_grad():
            for inputs, labels in test_loader:
                inputs, labels = inputs.to(device), labels.to(device)
                outputs = model(inputs)
                _, preds = torch.max(outputs, 1)
                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())

        base_acc, base_f1 = calculate_metrics(all_labels, all_preds)
        update_job_metrics(mongodb_uri, job_id, {
            "baseline_accuracy": float(base_acc),
            "baseline_macro_f1": float(base_f1)
        })
        logger.info(f"[MODEL] Current Accuracy: {base_acc * 100:.2f}%")
        logger.info(f"[MODEL] Current Macro F1: {base_f1:.4f}")

        # 5. Training
        update_job_status(mongodb_uri, job_id, "TRAINING", log_tail="Starting training phase")
        logger.info("[TRAIN] Starting real PyTorch fine-tuning")
        criterion = nn.CrossEntropyLoss()

        def log_epoch_result(epoch_idx, running_loss, correct, total, epoch_time, lr):
            epoch_loss = running_loss / total if total > 0 else 0.0
            epoch_acc = correct / total if total > 0 else 0.0
            logger.info("-" * 40)
            logger.info(f"Epoch {epoch_idx + 1}/{epochs}")
            logger.info(f"Train Loss: {epoch_loss:.4f}")
            logger.info(f"Train Accuracy: {epoch_acc * 100:.2f}%")
            logger.info(f"Learning Rate: {lr:.6f}")
            logger.info(f"Time: {epoch_time:.2f} sec")
            logger.info("-" * 40)

        # Phase 1: Train only head
        for param in model.features.parameters():
            param.requires_grad = False

        optimizer = optim.AdamW(model.classifier.parameters(), lr=1e-3)
        warmup_epochs = min(2, epochs)

        for epoch in range(warmup_epochs):
            model.train()
            epoch_start = time.time()
            running_loss = 0.0
            correct = 0
            total = 0
            for inputs, labels in train_loader:
                inputs, labels = inputs.to(device), labels.to(device)
                optimizer.zero_grad()
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()

                running_loss += loss.item() * inputs.size(0)
                _, batch_preds = torch.max(outputs, 1)
                correct += (batch_preds == labels).sum().item()
                total += labels.size(0)

            update_job_metrics(mongodb_uri, job_id, {"epochs_completed": epoch + 1})
            log_epoch_result(epoch, running_loss, correct, total, time.time() - epoch_start, optimizer.param_groups[0]["lr"])

        # Phase 2: Train all
        if epochs > warmup_epochs:
            for param in model.features.parameters():
                param.requires_grad = True

            optimizer = optim.AdamW(model.parameters(), lr=1e-4)
            scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs-warmup_epochs)

            for epoch in range(warmup_epochs, epochs):
                model.train()
                epoch_start = time.time()
                running_loss = 0.0
                correct = 0
                total = 0
                for inputs, labels in train_loader:
                    inputs, labels = inputs.to(device), labels.to(device)
                    optimizer.zero_grad()
                    outputs = model(inputs)
                    loss = criterion(outputs, labels)
                    loss.backward()
                    optimizer.step()

                    running_loss += loss.item() * inputs.size(0)
                    _, batch_preds = torch.max(outputs, 1)
                    correct += (batch_preds == labels).sum().item()
                    total += labels.size(0)

                scheduler.step()
                update_job_metrics(mongodb_uri, job_id, {"epochs_completed": epoch + 1})
                log_epoch_result(epoch, running_loss, correct, total, time.time() - epoch_start, optimizer.param_groups[0]["lr"])

        # 6. Evaluate Candidate
        update_job_status(mongodb_uri, job_id, "EVALUATING", log_tail="Evaluating candidate model...")
        logger.info("[EVAL] Evaluating candidate model...")
        model.eval()
        all_preds = []
        all_labels = []
        with torch.no_grad():
            for inputs, labels in test_loader:
                inputs, labels = inputs.to(device), labels.to(device)
                outputs = model(inputs)
                _, preds = torch.max(outputs, 1)
                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())

        cand_acc, cand_f1 = calculate_metrics(all_labels, all_preds)
        logger.info(f"[EVAL] Candidate Accuracy: {cand_acc * 100:.2f}%")
        logger.info(f"[EVAL] Candidate Macro F1: {cand_f1:.4f}")

        # Save candidate checkpoint
        logger.info("[CANDIDATE] Fine-tuning completed")
        logger.info("[CANDIDATE] Saving new candidate checkpoint...")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        candidate_name = f"candidate_{timestamp}_{job_id[:8]}.pth"
        candidates_dir = os.path.join(backend_dir, "models", "candidates")
        os.makedirs(candidates_dir, exist_ok=True)
        candidate_path = os.path.join(candidates_dir, candidate_name)

        deployed_checkpoint_name = "PaddyGuard_active_learning_round2.pth"
        if candidate_name == deployed_checkpoint_name:
            raise RuntimeError("Refusing to overwrite the deployed checkpoint with a candidate checkpoint")

        torch.save({"model_state_dict": model.state_dict()}, candidate_path)
        candidate_exists = os.path.exists(candidate_path)
        candidate_size_mb = os.path.getsize(candidate_path) / (1024 * 1024) if candidate_exists else 0.0
        logger.info(f"[CANDIDATE] Candidate checkpoint: {candidate_path}")
        logger.info(f"[CANDIDATE] File exists: {'Yes' if candidate_exists else 'No'}")
        logger.info(f"[CANDIDATE] File size: {candidate_size_mb:.2f} MB")
        logger.info(f"[CANDIDATE] Deployed checkpoint preserved (not overwritten): {deployed_checkpoint_name}")

        acc_delta = cand_acc - base_acc
        f1_delta = cand_f1 - base_f1

        is_better = (cand_acc > base_acc) and (cand_f1 >= base_f1)
        decision = "ELIGIBLE_FOR_PROMOTION" if is_better else "REJECTED_BY_METRICS"

        update_job_metrics(mongodb_uri, job_id, {
            "candidate_checkpoint": candidate_path,
            "candidate_accuracy": float(cand_acc),
            "candidate_macro_f1": float(cand_f1),
            "accuracy_delta": float(acc_delta),
            "f1_delta": float(f1_delta)
        })

        logger.info("=" * 40)
        logger.info("CURRENT MODEL VS CANDIDATE")
        logger.info("=" * 40)
        logger.info(f"Current Accuracy: {base_acc * 100:.2f}%")
        logger.info(f"Candidate Accuracy: {cand_acc * 100:.2f}%")
        logger.info(f"Accuracy Delta: {acc_delta * 100:+.2f} percentage points")
        logger.info(f"Current Macro F1: {base_f1:.4f}")
        logger.info(f"Candidate Macro F1: {cand_f1:.4f}")
        logger.info(f"Macro F1 Delta: {f1_delta:+.4f}")

        if is_better:
            logger.info("[DECISION] CANDIDATE ELIGIBLE FOR PROMOTION")
            logger.info("[DECISION] Waiting for Super Admin approval")
            logger.info("[DECISION] Candidate has NOT been automatically deployed")
        else:
            logger.info("[DECISION] CANDIDATE REJECTED")
            logger.info("[DECISION] Current deployed model remains unchanged")

        update_job_status(mongodb_uri, job_id, "COMPLETED", log_tail=f"Candidate Acc: {cand_acc:.4f}, F1: {cand_f1:.4f}", decision=decision)

        job_duration = time.time() - job_start_time
        logger.info("=" * 40)
        logger.info("FINE-TUNING JOB COMPLETE")
        logger.info("=" * 40)
        logger.info(f"Job ID: {job_id}")
        logger.info("Status: COMPLETED")
        logger.info(f"Samples used: {len(samples)}")
        logger.info(f"Candidate checkpoint: {candidate_name}")
        logger.info(f"Accuracy: {cand_acc * 100:.2f}%")
        logger.info(f"Macro F1: {cand_f1:.4f}")
        logger.info(f"Decision: {decision}")
        logger.info(f"Duration: {job_duration:.2f} sec")

    except Exception as e:
        job_duration = time.time() - job_start_time
        logger.error("=" * 40)
        logger.error("FINE-TUNING JOB FAILED")
        logger.error("=" * 40)
        logger.error(f"Job ID: {job_id}")
        logger.error(f"Duration: {job_duration:.2f} sec")
        logger.error(f"Training failed: {e}", exc_info=True)
        update_job_status(mongodb_uri, job_id, "FAILED", error=str(e), log_tail=f"Error: {str(e)}")
        sys.exit(1)
        
    finally:
        # Clean up temporary training directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary workspace folder: {temp_dir}")
            except Exception as e:
                logger.error(f"Failed to clean temporary workspace: {e}")

if __name__ == "__main__":
    main()
