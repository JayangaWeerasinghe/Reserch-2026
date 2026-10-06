from datetime import datetime

from app.repositories.prediction_repository import PredictionRepository


def test_verified_case_without_approved_flag_is_eligible():
    record = {
        "review_status": "verified",
        "expert_validated_disease": "Brown_Spot",
        "status": "KNOWN",
        "approved_for_training": None,
    }

    assert PredictionRepository.is_active_learning_eligible(record) is True


def test_unverified_or_blank_label_is_not_eligible():
    assert PredictionRepository.is_active_learning_eligible({
        "review_status": "pending",
        "expert_validated_disease": "Brown_Spot",
        "status": "KNOWN",
    }) is False

    assert PredictionRepository.is_active_learning_eligible({
        "review_status": "verified",
        "expert_validated_disease": "",
        "status": "KNOWN",
        "approved_for_training": True,
    }) is False


def test_ood_expert_verification_is_not_eligible_for_training():
    assert PredictionRepository.is_active_learning_eligible({
        "review_status": "verified",
        "expert_validated_disease": "OOD",
        "status": "OOD",
        "approved_for_training": True,
    }) is False

    assert PredictionRepository.is_approved_for_training({
        "review_status": "verified",
        "expert_validated_disease": "OOD",
        "status": "OOD",
        "approved_for_training": True,
    }) is False


def test_mongo_count_flow_for_verified_approved_and_consumed_samples():
    repo = PredictionRepository()
    case_id = "REGRESSION_TEST_PENDING_001"
    repo.collection.delete_many({"case_id": case_id})
    try:
        repo.collection.insert_one({
            "case_id": case_id,
            "status": "KNOWN",
            "review_status": "pending",
            "needs_expert_review": True,
            "review_reason": "LOW_CONFIDENCE",
            "approved_for_training": False,
            "consumed_by_job_id": None,
            "expert_validated_disease": None,
            "created_at": datetime.utcnow(),
        })

        assert repo.count_pending_expert_reviews() >= 1

        repo.update(case_id, {
            "review_status": "verified",
            "approved_for_training": True,
            "expert_validated_disease": "Brown_Spot",
            "verified_at": datetime.utcnow(),
            "expert_reviewed_at": datetime.utcnow(),
            "consumed_by_job_id": None,
            "needs_expert_review": False,
            "review_reason": "VERIFIED_BY_EXPERT",
        })

        assert repo.count_verified_expert_samples() >= 1
        assert repo.count_approved_for_training_samples() >= 1
        assert repo.count_active_learning_eligible() >= 1
        assert repo.count_consumed_training_samples() >= 0
        assert any(sample.case_id == case_id for sample in repo.find_verified_unused_samples())

        repo.update(case_id, {"consumed_by_job_id": "FT-TEST-123"})

        assert repo.count_active_learning_eligible() >= 0
        assert repo.count_consumed_training_samples() >= 1
    finally:
        repo.collection.delete_many({"case_id": case_id})


if __name__ == "__main__":
    test_verified_case_without_approved_flag_is_eligible()
    test_unverified_or_blank_label_is_not_eligible()
    test_mongo_count_flow_for_verified_approved_and_consumed_samples()
    print("mongo regression checks passed")
