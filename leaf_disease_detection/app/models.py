from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.sql import func
from .database import Base

class PredictionCase(Base):
    __tablename__ = "prediction_cases"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    image_name = Column(String)
    gradcam_image_name = Column(String, nullable=True)
    predicted_disease = Column(String)
    confidence = Column(Float)
    status = Column(String)
    severity_percentage = Column(Float)
    severity_level = Column(String)

    city = Column(String)
    district = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)

    field_area_acres = Column(Float)
    affected_field_percentage = Column(Float)
    rice_variety = Column(String)
    growth_stage = Column(String)
    expected_yield_kg_per_acre = Column(Float)
    treatment_applied = Column(Boolean, default=False)

    weather_json = Column(Text)
    predicted_loss_percentage = Column(Float)
    estimated_loss_kg = Column(Float)

    farmer_confirmation = Column(String)
    expert_validated_disease = Column(String)
    actual_harvest_kg = Column(Float)
    expected_healthy_harvest_kg = Column(Float)
    approved_for_training = Column(Boolean, default=False)
    is_low_confidence = Column(Boolean, default=False)
    energy_score = Column(Float)

    # Expert Review fields
    needs_expert_review = Column(Boolean, default=False)
    review_status = Column(String, default="pending")  # 'pending', 'verified'
    review_reason = Column(String, nullable=True) # 'LOW_CONFIDENCE', 'TOP_K_UNCERTAINTY'
    verified_at = Column(DateTime(timezone=True), nullable=True)

    # In-app fine-tuning tracking: set to job_id when consumed, NULL = available
    consumed_by_job_id = Column(String, nullable=True)

class ActiveLearningBatch(Base):
    __tablename__ = "active_learning_batches"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    sample_count = Column(Integer)
    status = Column(String, default="READY")  # 'READY', 'TRAINING_SIMULATION', 'WAITING_APPROVAL'
    is_demo_mode = Column(Boolean, default=False)
    recommended_batch_size = Column(Integer, default=100)
    source = Column(String, default="EXPERT_VERIFIED_ACTIVE_LEARNING")
    exported_at = Column(DateTime(timezone=True), nullable=True)
    export_count = Column(Integer, default=0)

class ActiveLearningBatchSample(Base):
    __tablename__ = "active_learning_batch_samples"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String, index=True, nullable=False)
    case_id = Column(String, index=True, nullable=False)
    added_at = Column(DateTime(timezone=True), server_default=func.now())

class CandidateModel(Base):
    __tablename__ = "candidate_models"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(String, unique=True, index=True, nullable=False)
    filename = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    test_accuracy = Column(Float, nullable=False)
    macro_f1 = Column(Float, nullable=False)
    source_batch_id = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String, nullable=False) # 'VALIDATED', 'REJECTED_BY_METRICS', 'ELIGIBLE_FOR_REVIEW'
    training_job_id = Column(String, nullable=True)  # Link to in-app training job
    checkpoint_pruned_at = Column(DateTime(timezone=True), nullable=True)

class ExpertUser(Base):
    __tablename__ = "expert_users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="EXPERT") # "EXPERT"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(String, nullable=True)

class TrainingJob(Base):
    """Tracks in-app Active Learning fine-tuning jobs."""
    __tablename__ = "training_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, default="QUEUED")
    # QUEUED → PREPARING → TRAINING → EVALUATING → COMPLETED / FAILED
    # COMPLETED decision: ELIGIBLE_FOR_PROMOTION or REJECTED_BY_METRICS
    # After manual promote: PROMOTED

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # subprocess writes these as ISO strings directly via sqlite3
    started_at = Column(String, nullable=True)
    completed_at = Column(String, nullable=True)

    source_sample_count = Column(Integer, nullable=True)
    base_checkpoint = Column(String, nullable=False)
    candidate_checkpoint = Column(String, nullable=True)

    baseline_accuracy = Column(Float, nullable=True)
    baseline_macro_f1 = Column(Float, nullable=True)
    candidate_accuracy = Column(Float, nullable=True)
    candidate_macro_f1 = Column(Float, nullable=True)
    accuracy_delta = Column(Float, nullable=True)
    f1_delta = Column(Float, nullable=True)

    decision = Column(String, nullable=True)
    # ELIGIBLE_FOR_PROMOTION, REJECTED_BY_METRICS, FAILED
    error_message = Column(Text, nullable=True)
    log_tail = Column(Text, nullable=True)   # last ~10 lines of training log
    epochs_completed = Column(Integer, default=0)
    total_epochs = Column(Integer, nullable=True)

class DeployedModelRecord(Base):
    """Persists the currently active model and its real evaluation metrics.
    All future fine-tuning rounds compare against the latest active record.
    """
    __tablename__ = "deployed_model_records"

    id = Column(Integer, primary_key=True, index=True)
    checkpoint_path = Column(String, nullable=False)
    test_accuracy = Column(Float, nullable=False)
    macro_f1 = Column(Float, nullable=False)
    deployed_at = Column(DateTime(timezone=True), server_default=func.now())
    deployed_by = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

