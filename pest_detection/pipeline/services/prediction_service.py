import logging

from PIL import Image

from pipeline.core.config import Settings
from pipeline.ml.model_loader import DenseNet121Classifier
from pipeline.ml.gradcam import GradCAM
from pipeline.ml.few_shot import FewShotStore
from pipeline.ml.few_shot_finetune import SelectiveFineTuner
from pipeline.services.image_quality import ImageQualityService
from pipeline.ml.ood import MahalanobisOOD


logger = logging.getLogger(__name__)


class PredictionService:
    """
    Main prediction orchestration service.

    Pipeline:

        Image
          ↓
        Quality Check
          ↓
        DenseNet121 Base Prediction
          ↓
        OOD Detection
          ↓
        Few-Shot / Fine-Tuned Matching
          ↓
        Final Prediction
          ↓
        Grad-CAM Explanation
    """

    def __init__(
        self,
        settings: Settings,
        classifier: DenseNet121Classifier,
        quality_service: ImageQualityService,
    ):

        self.s = settings

        self.classifier = classifier

        self.quality_service = quality_service


        # ----------------------------------------------------
        # Base DenseNet121 Grad-CAM
        # ----------------------------------------------------

        self.gradcam = GradCAM(
            classifier.model
        )


        # ----------------------------------------------------
        # Mahalanobis OOD
        # ----------------------------------------------------

        self.ood = MahalanobisOOD(

            settings.ood_reference_path,

            settings.ood_mahalanobis_threshold
        )


        # ----------------------------------------------------
        # Prototype Few-Shot Store
        # ----------------------------------------------------

        self.few_shot = FewShotStore(

            classifier,

            settings.few_shot_store_dir,

            settings.few_shot_similarity_threshold
        )


        # ----------------------------------------------------
        # Selective Fine-Tuning
        # ----------------------------------------------------

        self.fine_tuner = SelectiveFineTuner(

            classifier,

            settings.fine_tuned_store_dir,

            settings.image_size,

            settings.fine_tune_epochs,

            settings.fine_tune_learning_rate,

            settings.fine_tune_confidence_threshold
        )


    # ========================================================
    # MAIN PREDICTION
    # ========================================================

    def predict(
        self,
        image: Image.Image
    ):

        # ====================================================
        # STEP 1
        # IMAGE QUALITY CHECK
        # ====================================================

        quality = (
            self.quality_service
            .evaluate(image)
        )


        if not quality.passed:

            return {

                "prediction":
                    "Image Quality Too Low",

                "confidence":
                    0.0,

                "status":
                    "unknown",

                "source":
                    "quality_check",

                "quality":
                    quality,

                "gradcam_image_base64":
                    None,

                "message":
                    (
                        "Please capture a clearer "
                        "pest image before diagnosis."
                    ),

                "few_shot_similarity":
                    None,

                "ood_score":
                    None,

                "ood_method":
                    (
                        "Mahalanobis"
                        if self.ood.ready
                        else
                        "confidence-threshold fallback"
                    ),
            }


        # ====================================================
        # STEP 2
        # BASE DENSENET121 PREDICTION
        # ====================================================

        result = self.classifier.predict(
            image
        )


        confidence = float(
            result["confidence"]
        )


        # ====================================================
        # STEP 3
        # OOD DETECTION
        # ====================================================

        ood_unknown = False

        ood_score = None


        if self.ood.ready:

            embedding = (
                self.classifier
                .extract_embedding(image)
            )


            ood_unknown, ood_score = (
                self.ood.is_unknown(
                    embedding
                )
            )


        # ====================================================
        # STEP 4
        # FEW-SHOT / FINE-TUNED CHECK
        # ====================================================

        few_shot_match = None

        fine_tuned_match = None


        # New learned classes are checked when:
        #
        # 1. Base model confidence is low
        # OR
        # 2. OOD detector says unknown
        #

        if (
            confidence
            < self.s.maybe_threshold
            or ood_unknown
        ):

            # ------------------------------------------------
            # First try selective fine-tuning
            # ------------------------------------------------

            fine_tuned_match = (
                self.fine_tuner.predict(
                    image
                )
            )


            # ------------------------------------------------
            # If no fine-tuned class matches,
            # try prototype few-shot learning.
            # ------------------------------------------------

            if not fine_tuned_match:

                few_shot_match = (
                    self.few_shot.classify(
                        image
                    )
                )


        # ====================================================
        # STEP 5
        # SELECT FINAL RESULT
        # ====================================================

        target_model = None

        target_index = None

        gradcam_tensor = None


        # ----------------------------------------------------
        # CASE A
        # SELECTIVE FINE-TUNED NEW PEST
        # ----------------------------------------------------

        if fine_tuned_match:

            status = "known"

            prediction = (
                fine_tuned_match[
                    "class_name"
                ]
            )

            message = (
                "Pest recognized by the "
                "selectively fine-tuned "
                "DenseNet121 adapter."
            )

            display_confidence = (
                fine_tuned_match[
                    "confidence"
                ]
            )

            source = "fine_tuned"


            target_index = (
                fine_tuned_match[
                    "index"
                ]
            )


            target_model = (
                fine_tuned_match[
                    "model"
                ]
            )


            # IMPORTANT:
            # Use the normal tensor returned by
            # SelectiveFineTuner.predict().
            #
            # Do NOT create a new tensor inside
            # inference_mode.

            gradcam_tensor = (
                fine_tuned_match.get(
                    "input_tensor"
                )
            )


        # ----------------------------------------------------
        # CASE B
        # MAHALANOBIS OOD UNKNOWN
        # ----------------------------------------------------

        elif (
            ood_unknown
            and not few_shot_match
        ):

            status = "unknown"

            prediction = "Unknown Pest"

            message = (
                "Mahalanobis OOD detection "
                "rejected this image as outside "
                "the learned pest distribution."
            )

            display_confidence = confidence

            source = "ood"


            target_index = (
                result["index"]
            )


            target_model = (
                self.classifier.model
            )


        # ----------------------------------------------------
        # CASE C
        # PROTOTYPE FEW-SHOT
        # ----------------------------------------------------

        elif few_shot_match:

            status = "known"

            prediction = (
                few_shot_match[
                    "class_name"
                ]
            )

            message = (
                "Pest matched a user-learned "
                "few-shot class."
            )

            display_confidence = (
                few_shot_match[
                    "similarity"
                ]
            )

            source = "few_shot"


            target_index = (
                result["index"]
            )


            target_model = (
                self.classifier.model
            )


        # ----------------------------------------------------
        # CASE D
        # UNKNOWN BASE MODEL
        # ----------------------------------------------------

        elif (
            confidence
            < self.s.unknown_threshold
        ):

            status = "unknown"

            prediction = "Unknown Pest"

            message = (
                "The image does not confidently "
                "match the trained or learned "
                "pest classes."
            )

            display_confidence = confidence

            source = "base_model"


            target_index = (
                result["index"]
            )


            target_model = (
                self.classifier.model
            )


        # ----------------------------------------------------
        # CASE E
        # MODERATE CONFIDENCE
        # ----------------------------------------------------

        elif (
            confidence
            < self.s.maybe_threshold
        ):

            status = "maybe"

            prediction = (
                f"Maybe: "
                f"{result['class_name']}"
            )

            message = (
                "Prediction confidence is "
                "moderate. Please verify "
                "the image."
            )

            display_confidence = confidence

            source = "base_model"


            target_index = (
                result["index"]
            )


            target_model = (
                self.classifier.model
            )


        # ----------------------------------------------------
        # CASE F
        # NORMAL KNOWN PEST
        # ----------------------------------------------------

        else:

            status = "known"

            prediction = (
                result["class_name"]
            )

            message = (
                "Pest detected successfully."
            )

            display_confidence = confidence

            source = "base_model"


            target_index = (
                result["index"]
            )


            target_model = (
                self.classifier.model
            )


        # ====================================================
        # STEP 6
        # GRAD-CAM EXPLANATION
        # ====================================================

        heatmap = None


        # Grad-CAM is useful for known / maybe results.
        # We do not force Grad-CAM for rejected unknown images.

        if (
            status != "unknown"
            and target_model is not None
            and target_index is not None
        ):

            try:

                # ------------------------------------------------
                # Fine-tuned model
                # ------------------------------------------------

                if source == "fine_tuned":

                    from pipeline.ml.gradcam import GradCAM


                    adapter_cam = GradCAM(
                        target_model
                    )


                    try:

                        # If SelectiveFineTuner returned
                        # a safe tensor, use it.
                        #
                        # Otherwise create a safe tensor.

                        if gradcam_tensor is None:

                            gradcam_tensor = (
                                self.classifier
                                .preprocess(
                                    image
                                )
                            )


                        gradcam_tensor = (
                            gradcam_tensor
                            .detach()
                            .clone()
                        )


                        heatmap = (
                            adapter_cam.generate(

                                image,

                                gradcam_tensor,

                                target_index
                            )
                        )


                    finally:

                        adapter_cam.close()


                # ------------------------------------------------
                # Base DenseNet121 model
                # ------------------------------------------------

                else:

                    if gradcam_tensor is None:

                        gradcam_tensor = (
                            self.classifier
                            .preprocess(
                                image
                            )
                        )


                    gradcam_tensor = (
                        gradcam_tensor
                        .detach()
                        .clone()
                    )


                    heatmap = (
                        self.gradcam.generate(

                            image,

                            gradcam_tensor,

                            target_index
                        )
                    )


            except Exception as exc:

                # ------------------------------------------------
                # IMPORTANT:
                #
                # Grad-CAM failure should NOT destroy the
                # actual pest prediction.
                #
                # Prediction remains valid, but the explanation
                # becomes unavailable.
                # ------------------------------------------------

                logger.exception(
                    "Grad-CAM generation failed: %s",
                    exc
                )

                heatmap = None


        # ====================================================
        # STEP 7
        # FEW-SHOT SIMILARITY
        # ====================================================

        if few_shot_match:

            few_shot_similarity = round(
                float(
                    few_shot_match[
                        "similarity"
                    ]
                ),
                4
            )

        elif fine_tuned_match:

            few_shot_similarity = round(
                float(
                    fine_tuned_match[
                        "confidence"
                    ]
                ),
                4
            )

        else:

            few_shot_similarity = None


        # ====================================================
        # STEP 8
        # FINAL RESPONSE
        # ====================================================

        return {

            "prediction":
                prediction,

            "confidence":
                round(
                    float(
                        display_confidence
                    ),
                    4
                ),

            "status":
                status,

            "source":
                source,

            "quality":
                quality,

            "gradcam_image_base64":
                heatmap,

            "message":
                message,

            "few_shot_similarity":
                few_shot_similarity,

            "ood_score":
                (
                    round(
                        float(ood_score),
                        4
                    )
                    if ood_score is not None
                    else None
                ),

            "ood_method":
                (
                    "Mahalanobis"
                    if self.ood.ready
                    else
                    "confidence-threshold fallback"
                ),
        }