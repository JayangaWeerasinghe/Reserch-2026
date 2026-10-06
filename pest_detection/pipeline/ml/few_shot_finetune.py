import io
import logging
import re
from pathlib import Path

import torch
import torch.nn as nn
from PIL import Image
from torchvision import transforms
from torch.utils.data import Dataset, DataLoader

logger = logging.getLogger(__name__)


# ============================================================
# DATASET
# ============================================================

class FewShotImageDataset(Dataset):

    def __init__(
        self,
        images,
        label=0,
        transform=None,
        repeats=20
    ):
        self.images = images
        self.label = label
        self.transform = transform
        self.repeats = max(1, repeats)

    def __len__(self):
        return len(self.images) * self.repeats

    def __getitem__(self, idx):

        image = self.images[
            idx % len(self.images)
        ].copy()

        if self.transform:
            image = self.transform(image)

        return image, self.label


# ============================================================
# SELECTIVE FINE-TUNER
# ============================================================

class SelectiveFineTuner:
    """
    Selective fine-tuning adapter for newly discovered pests.

    Original DenseNet121 model is NEVER overwritten.

    For a new pest:
        1. Safely clone the base DenseNet121.
        2. Add one new classifier output.
        3. Freeze the complete model.
        4. Fine-tune only:
              - denseblock4
              - norm5
              - classifier
        5. Save the adapted model separately.

    Supports 5-20 labelled images.
    """

    def __init__(
        self,
        base_classifier,
        store_dir,
        image_size=224,
        epochs=8,
        lr=1e-4,
        confidence_threshold=0.70
    ):

        self.base = base_classifier

        self.store_dir = Path(store_dir)

        self.store_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.image_size = image_size
        self.epochs = epochs
        self.lr = lr
        self.confidence_threshold = confidence_threshold

        self.adapters = {}

        self._load_all()


    # ========================================================
    # SAFE CLASS NAME
    # ========================================================

    @staticmethod
    def _safe_name(name):

        cleaned = re.sub(
            r"[^a-zA-Z0-9 _-]",
            "",
            name
        ).strip()

        if not cleaned:
            raise ValueError(
                "Pest class name is invalid."
            )

        return cleaned[:80]


    # ========================================================
    # CHECKPOINT PATH
    # ========================================================

    def _path(self, name):

        safe = (
            self._safe_name(name)
            .lower()
            .replace(" ", "_")
        )

        return self.store_dir / f"{safe}.pt"


    # ========================================================
    # LOAD SAVED ADAPTERS
    # ========================================================

    def _load_all(self):

        for path in self.store_dir.glob("*.pt"):

            try:

                payload = torch.load(
                    path,
                    map_location=self.base.device,
                    weights_only=True
                )

                self.adapters[
                    payload["class_name"]
                ] = payload

                logger.info(
                    "Loaded fine-tuned pest adapter: %s",
                    payload["class_name"]
                )

            except Exception as exc:

                logger.warning(
                    "Could not load fine-tuned adapter %s: %s",
                    path,
                    exc
                )


    # ========================================================
    # SAFE MODEL CLONE
    # ========================================================

    def _clone_base_model(self):
        """
        Create an independent copy of the base DenseNet121.

        deepcopy() is intentionally avoided because the model
        may contain parametrized/weight-normalized tensors.

        The model is serialized to memory and loaded again,
        creating a separate model object.
        """

        buffer = io.BytesIO()

        torch.save(
            self.base.model,
            buffer
        )

        buffer.seek(0)

        model = torch.load(
            buffer,
            map_location=self.base.device,
            weights_only=False
        )

        model = model.to(
            self.base.device
        )

        return model


    # ========================================================
    # BUILD ADAPTED MODEL
    # ========================================================

    def _build_adapted_model(self):

        model = self._clone_base_model()

        old_classifier = model.classifier

        old_out = (
            old_classifier[-1]
            .out_features
        )

        old_in = (
            old_classifier[-1]
            .in_features
        )

        # Add one new class
        new_out = old_out + 1

        new_classifier = nn.Sequential(

            nn.Dropout(
                p=0.5
            ),

            nn.Linear(
                old_in,
                new_out
            )
        )

        # Preserve original classifier knowledge
        with torch.no_grad():

            new_classifier[-1].weight[
                :old_out
            ].copy_(
                old_classifier[-1].weight
            )

            new_classifier[-1].bias[
                :old_out
            ].copy_(
                old_classifier[-1].bias
            )

            # New class starts with neutral weights
            new_classifier[-1].weight[
                old_out
            ].zero_()

            # Slight initial suppression
            new_classifier[-1].bias[
                old_out
            ] = -1.0

        model.classifier = new_classifier

        # ----------------------------------------------------
        # Freeze all layers
        # ----------------------------------------------------

        for parameter in model.parameters():
            parameter.requires_grad = False

        # ----------------------------------------------------
        # Selective fine-tuning
        # ----------------------------------------------------

        for parameter in (
            model.features
            .denseblock4
            .parameters()
        ):
            parameter.requires_grad = True

        for parameter in (
            model.features
            .norm5
            .parameters()
        ):
            parameter.requires_grad = True

        for parameter in (
            model.classifier
            .parameters()
        ):
            parameter.requires_grad = True

        return model.to(
            self.base.device
        )


    # ========================================================
    # IMAGE TRANSFORMS
    # ========================================================

    def _transform(self, train=True):

        if train:

            return transforms.Compose([

                transforms.Resize(
                    (
                        self.image_size,
                        self.image_size
                    )
                ),

                transforms.RandomHorizontalFlip(),

                transforms.RandomRotation(
                    15
                ),

                transforms.ColorJitter(
                    brightness=0.20,
                    contrast=0.20,
                    saturation=0.15
                ),

                transforms.ToTensor(),

            ])

        return transforms.Compose([

            transforms.Resize(
                (
                    self.image_size,
                    self.image_size
                )
            ),

            transforms.ToTensor(),

        ])


    # ========================================================
    # REGISTER / LEARN NEW PEST
    # ========================================================

    def register(
        self,
        class_name,
        images
    ):

        class_name = self._safe_name(
            class_name
        )

        if len(images) < 5 or len(images) > 20:

            raise ValueError(
                "Please provide between 5 and "
                "20 labelled images."
            )

        if class_name in self.adapters:

            raise ValueError(
                f"A fine-tuned class named "
                f"'{class_name}' already exists. "
                f"Delete it first."
            )

        logger.info(
            "Starting selective fine-tuning "
            "for '%s' using %d images",
            class_name,
            len(images)
        )

        model = self._build_adapted_model()

        # New class index
        new_class_index = len(
            self.base.CLASSES
        )

        dataset = FewShotImageDataset(

            images,

            label=new_class_index,

            transform=self._transform(
                train=True
            ),

            repeats=20
        )

        loader = DataLoader(

            dataset,

            batch_size=min(
                8,
                len(dataset)
            ),

            shuffle=True,

            num_workers=0
        )

        criterion = nn.CrossEntropyLoss()

        trainable_parameters = [
            parameter
            for parameter in model.parameters()
            if parameter.requires_grad
        ]

        optimizer = torch.optim.AdamW(

            trainable_parameters,

            lr=self.lr,

            weight_decay=1e-4
        )

        model.train()

        for epoch in range(
            self.epochs
        ):

            epoch_loss = 0.0

            for x, y in loader:

                x = x.to(
                    self.base.device
                )

                y = y.to(
                    self.base.device
                )

                optimizer.zero_grad(
                    set_to_none=True
                )

                logits = model(x)

                loss = criterion(
                    logits,
                    y
                )

                loss.backward()

                optimizer.step()

                epoch_loss += loss.item()

            logger.info(
                "Fine-tuning %s | Epoch %d/%d | Loss %.4f",
                class_name,
                epoch + 1,
                self.epochs,
                epoch_loss / max(
                    1,
                    len(loader)
                )
            )

        model.eval()

        # ----------------------------------------------------
        # SAVE ADAPTED MODEL
        # ----------------------------------------------------

        payload = {

            "class_name":
                class_name,

            "images_used":
                len(images),

            "epochs":
                self.epochs,

            "fine_tuned_layers": [

                "denseblock4",

                "norm5",

                "classifier"

            ],

            "base_classes":
                list(self.base.CLASSES),

            "new_class_index":
                new_class_index,

            "state_dict":
                model.state_dict(),

        }

        checkpoint_path = self._path(
            class_name
        )

        torch.save(
            payload,
            checkpoint_path
        )

        self.adapters[
            class_name
        ] = payload

        logger.info(
            "Successfully saved adapted pest "
            "model: %s",
            checkpoint_path
        )

        return {

            "class_name":
                class_name,

            "images_used":
                len(images),

            "epochs":
                self.epochs,

            "fine_tuned_layers":
                payload[
                    "fine_tuned_layers"
                ],

            "message":
                (
                    f"New pest '{class_name}' "
                    f"learned using selective "
                    f"fine-tuning from "
                    f"{len(images)} labelled images."
                ),

        }


    # ========================================================
    # LOAD ADAPTED MODEL
    # ========================================================

    def _load_model(self, payload):

        model = self._clone_base_model()

        old_classifier = model.classifier

        old_out = (
            old_classifier[-1]
            .out_features
        )

        old_in = (
            old_classifier[-1]
            .in_features
        )

        model.classifier = nn.Sequential(

            nn.Dropout(
                p=0.5
            ),

            nn.Linear(
                old_in,
                old_out + 1
            )

        )

        model.load_state_dict(
            payload["state_dict"],
            strict=True
        )

        model = model.to(
            self.base.device
        )

        model.eval()

        return model


    # ========================================================
    # PREDICT NEW FEW-SHOT PEST
    # ========================================================

    def predict(self, image):
        """
        IMPORTANT:
        Do NOT use @torch.inference_mode() here.

        Grad-CAM needs a normal autograd-compatible tensor.
        The prediction itself is still performed with gradients
        disabled using torch.no_grad(), while the returned
        input tensor remains compatible with Grad-CAM.
        """

        best = None

        for (
            class_name,
            payload
        ) in self.adapters.items():

            try:

                model = self._load_model(
                    payload
                )

                # ------------------------------------------------
                # IMPORTANT:
                # Do NOT create the preprocessing tensor inside
                # torch.inference_mode().
                # Grad-CAM may need this tensor later.
                # ------------------------------------------------

                tensor = self.base.preprocess(
                    image
                )

                # Make sure this is a normal tensor.
                tensor = (
                    tensor
                    .detach()
                    .clone()
                )

                # Prediction only
                with torch.no_grad():

                    logits = model(
                        tensor
                    )

                    probs = torch.softmax(
                        logits,
                        dim=1
                    )[0]

                new_class_index = (
                    payload.get(
                        "new_class_index",
                        len(
                            self.base.CLASSES
                        )
                    )
                )

                new_prob = float(
                    probs[
                        new_class_index
                    ].item()
                )

                if (
                    best is None
                    or new_prob >
                    best["confidence"]
                ):

                    best = {

                        "class_name":
                            class_name,

                        "confidence":
                            new_prob,

                        "model":
                            model,

                        "index":
                            new_class_index,

                        # Return a normal tensor
                        # for Grad-CAM.
                        "input_tensor":
                            tensor,

                    }

            except Exception as exc:

                logger.exception(
                    "Could not predict using "
                    "adapter '%s': %s",
                    class_name,
                    exc
                )

        if (
            best
            and best["confidence"]
            >= self.confidence_threshold
        ):

            return best

        return None


    # ========================================================
    # LIST LEARNED CLASSES
    # ========================================================

    def list_classes(self):

        return sorted(
            self.adapters.keys()
        )


    # ========================================================
    # DELETE LEARNED CLASS
    # ========================================================

    def delete(
        self,
        class_name
    ):

        class_name = self._safe_name(
            class_name
        )

        path = self._path(
            class_name
        )

        removed = (
            self.adapters.pop(
                class_name,
                None
            )
            is not None
        )

        if path.exists():

            path.unlink()

            removed = True

        return removed