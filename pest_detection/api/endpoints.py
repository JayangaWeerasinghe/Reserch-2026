import io
import logging

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
    Depends,
)

from PIL import Image, UnidentifiedImageError

from pipeline.core.config import Settings, get_settings
from pipeline.ml.model_loader import DenseNet121Classifier

from schemas.health import HealthResponse
from schemas.prediction import PredictionResponse
from schemas.few_shot import (
    FewShotRegisterResponse,
    FewShotClassesResponse,
)

from pipeline.services.image_quality import ImageQualityService
from pipeline.services.prediction_service import PredictionService


router = APIRouter()

logger = logging.getLogger(__name__)


_classifier: DenseNet121Classifier | None = None
_service: PredictionService | None = None


# ============================================================
# SERVICE
# ============================================================

def get_service(
    settings: Settings = Depends(get_settings),
) -> PredictionService:

    global _classifier, _service

    if _service is None:

        _classifier = DenseNet121Classifier(
            settings
        )

        _service = PredictionService(
            settings,
            _classifier,
            ImageQualityService(settings),
        )

    return _service


# ============================================================
# HEALTH CHECK
# ============================================================

@router.get(
    "/health",
    response_model=HealthResponse,
)
def health(
    settings: Settings = Depends(get_settings),
    service: PredictionService = Depends(get_service),
):

    return HealthResponse(
        status="ok",
        model_loaded=(
            service.classifier.model is not None
        ),
        device=str(
            service.classifier.device
        ),
        model_name="DenseNet121",
    )


# ============================================================
# NORMAL PEST PREDICTION
# ============================================================

@router.post(
    "/predict",
    response_model=PredictionResponse,
)
async def predict(
    file: UploadFile = File(...),

    settings: Settings = Depends(
        get_settings
    ),

    service: PredictionService = Depends(
        get_service
    ),
):

    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }


    # Validate file type

    if file.content_type not in allowed_types:

        raise HTTPException(
            status_code=415,
            detail=(
                "Only JPEG, PNG, and WEBP "
                "images are supported."
            ),
        )


    # Read image

    contents = await file.read()

    max_bytes = (
        settings.max_upload_size_mb
        * 1024
        * 1024
    )


    if len(contents) > max_bytes:

        raise HTTPException(
            status_code=413,
            detail=(
                "Image is too large. "
                f"Maximum size is "
                f"{settings.max_upload_size_mb} MB."
            ),
        )


    if not contents:

        raise HTTPException(
            status_code=400,
            detail="Uploaded image is empty.",
        )


    # Convert to PIL Image

    try:

        image = Image.open(
            io.BytesIO(contents)
        ).convert("RGB")

    except (
        UnidentifiedImageError,
        OSError,
    ) as exc:

        logger.warning(
            "Invalid image upload: %s",
            exc,
        )

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid or corrupted "
                "image file."
            ),
        ) from exc


    # Prediction

    try:

        return service.predict(image)

    except RuntimeError as exc:

        logger.exception(
            "Model inference failed"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Model inference failed. "
                "Check server logs."
            ),
        ) from exc


# ============================================================
# FEW-SHOT LEARNED CLASSES
# ============================================================

@router.get(
    "/few-shot/classes",
    response_model=FewShotClassesResponse,
)
def few_shot_classes(
    service: PredictionService = Depends(
        get_service
    ),
):

    prototype_classes = set(
        service.few_shot.list_classes()
    )

    fine_tuned_classes = set(
        service.fine_tuner.list_classes()
    )

    classes = sorted(
        prototype_classes
        | fine_tuned_classes
    )

    return FewShotClassesResponse(
        classes=classes
    )


# ============================================================
# PROTOTYPE FEW-SHOT LEARNING
# ============================================================

@router.post(
    "/few-shot/register",
    response_model=FewShotRegisterResponse,
)
async def register_few_shot(

    # IMPORTANT:
    # React FormData sends class_name as a form field.
    class_name: str = Form(...),

    files: list[UploadFile] = File(...),

    settings: Settings = Depends(
        get_settings
    ),

    service: PredictionService = Depends(
        get_service
    ),
):

    # Validate image count

    if len(files) < 5 or len(files) > 20:

        raise HTTPException(
            status_code=400,
            detail=(
                "Upload between 5 and "
                "20 labelled images."
            ),
        )


    # Validate class name

    if not class_name.strip():

        raise HTTPException(
            status_code=400,
            detail=(
                "Please provide a new "
                "pest name."
            ),
        )


    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }


    images = []

    max_bytes = (
        settings.max_upload_size_mb
        * 1024
        * 1024
    )


    # Read all images

    for file in files:

        if file.content_type not in allowed_types:

            raise HTTPException(
                status_code=415,
                detail=(
                    "Unsupported image type: "
                    f"{file.filename}"
                ),
            )


        contents = await file.read()


        if not contents:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Image is empty: "
                    f"{file.filename}"
                ),
            )


        if len(contents) > max_bytes:

            raise HTTPException(
                status_code=413,
                detail=(
                    "Image is too large: "
                    f"{file.filename}"
                ),
            )


        try:

            image = Image.open(
                io.BytesIO(contents)
            ).convert("RGB")

            images.append(image)

        except (
            UnidentifiedImageError,
            OSError,
        ) as exc:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid image: "
                    f"{file.filename}"
                ),
            ) from exc


    # Register prototype

    try:

        return service.few_shot.register(
            class_name.strip(),
            images,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:

        logger.exception(
            "Prototype learning failed"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Prototype learning failed. "
                "Check server logs."
            ),
        ) from exc


# ============================================================
# SELECTIVE FINE-TUNING
# ============================================================

@router.post(
    "/few-shot/fine-tune",
    response_model=FewShotRegisterResponse,
)
async def fine_tune_new_pest(

    # IMPORTANT:
    # This MUST be Form(...)
    # because React sends FormData.

    class_name: str = Form(...),

    files: list[UploadFile] = File(...),

    settings: Settings = Depends(
        get_settings
    ),

    service: PredictionService = Depends(
        get_service
    ),
):

    # --------------------------------------------------------
    # Validate class name
    # --------------------------------------------------------

    if not class_name.strip():

        raise HTTPException(
            status_code=400,
            detail=(
                "Please enter a new pest name."
            ),
        )


    # --------------------------------------------------------
    # Validate number of images
    # --------------------------------------------------------

    if len(files) < 5 or len(files) > 20:

        raise HTTPException(
            status_code=400,
            detail=(
                "Upload between 5 and "
                "20 labelled images."
            ),
        )


    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }


    images = []

    max_bytes = (
        settings.max_upload_size_mb
        * 1024
        * 1024
    )


    # --------------------------------------------------------
    # Read uploaded images
    # --------------------------------------------------------

    for file in files:

        if file.content_type not in allowed_types:

            raise HTTPException(
                status_code=415,
                detail=(
                    "Unsupported image type: "
                    f"{file.filename}"
                ),
            )


        contents = await file.read()


        if not contents:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Image is empty: "
                    f"{file.filename}"
                ),
            )


        if len(contents) > max_bytes:

            raise HTTPException(
                status_code=413,
                detail=(
                    "Image is too large: "
                    f"{file.filename}"
                ),
            )


        try:

            image = Image.open(
                io.BytesIO(contents)
            ).convert("RGB")

            images.append(image)

        except (
            UnidentifiedImageError,
            OSError,
        ) as exc:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid image: "
                    f"{file.filename}"
                ),
            ) from exc


    # --------------------------------------------------------
    # SELECTIVE FINE-TUNING
    # --------------------------------------------------------

    try:

        result = service.fine_tuner.register(
            class_name=class_name.strip(),
            images=images,
        )

        return result


    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


    except RuntimeError as exc:

        logger.exception(
            "Selective fine-tuning failed"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Selective fine-tuning failed. "
                "Check server logs."
            ),
        ) from exc


    except Exception as exc:

        logger.exception(
            "Unexpected fine-tuning error"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unexpected error during "
                "fine-tuning. "
                "Check server logs."
            ),
        ) from exc


# ============================================================
# DELETE LEARNED CLASS
# ============================================================

@router.delete(
    "/few-shot/classes/{class_name}"
)
def delete_few_shot(
    class_name: str,

    service: PredictionService = Depends(
        get_service
    ),
):

    removed = service.few_shot.delete(
        class_name
    )


    fine_tuned_removed = (
        service.fine_tuner.delete(
            class_name
        )
    )


    removed = (
        fine_tuned_removed
        or removed
    )


    if not removed:

        raise HTTPException(
            status_code=404,
            detail=(
                "Few-shot class "
                "not found."
            ),
        )


    return {
        "message": (
            f"Few-shot class "
            f"'{class_name}' deleted."
        )
    }