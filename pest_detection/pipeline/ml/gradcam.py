import base64
from io import BytesIO

import cv2
import numpy as np
import torch
from PIL import Image


class GradCAM:
    """
    Grad-CAM implementation for DenseNet121.

    Uses the final convolution layer:
        denseblock4.denselayer16.conv2

    Important:
    Grad-CAM requires autograd, so inference_mode tensors
    are converted into normal tensors before forward/backward.
    """

    def __init__(self, model):

        self.model = model

        self.activations = None
        self.gradients = None

        # ----------------------------------------------------
        # Target layer
        # ----------------------------------------------------

        self.target_layer = (
            model
            .features
            .denseblock4
            .denselayer16
            .conv2
        )

        # ----------------------------------------------------
        # Forward hook
        # ----------------------------------------------------

        self.forward_handle = (
            self.target_layer.register_forward_hook(
                self._save_activation
            )
        )

        # ----------------------------------------------------
        # Backward hook
        # ----------------------------------------------------

        self.backward_handle = (
            self.target_layer.register_full_backward_hook(
                self._save_gradient
            )
        )


    # ========================================================
    # SAVE ACTIVATIONS
    # ========================================================

    def _save_activation(
        self,
        module,
        inputs,
        output
    ):

        self.activations = output


    # ========================================================
    # SAVE GRADIENTS
    # ========================================================

    def _save_gradient(
        self,
        module,
        grad_input,
        grad_output
    ):

        if grad_output is not None:

            self.gradients = grad_output[0]


    # ========================================================
    # GENERATE GRAD-CAM
    # ========================================================

    def generate(
        self,
        image: Image.Image,
        input_tensor: torch.Tensor,
        target_index: int
    ) -> str:

        # ----------------------------------------------------
        # IMPORTANT FIX
        #
        # Grad-CAM requires autograd.
        #
        # If the tensor came from torch.inference_mode(),
        # simply calling requires_grad_(True) can fail.
        #
        # detach().clone() creates a normal tensor.
        # ----------------------------------------------------

        input_tensor = (
            input_tensor
            .detach()
            .clone()
            .requires_grad_(True)
        )


        # Make sure model is in evaluation mode.
        # This keeps BatchNorm / Dropout behaviour stable.
        self.model.eval()


        # Clear previous hooks
        self.activations = None
        self.gradients = None


        # ----------------------------------------------------
        # Clear old gradients
        # ----------------------------------------------------

        self.model.zero_grad(
            set_to_none=True
        )


        # ----------------------------------------------------
        # Forward pass
        #
        # DO NOT use torch.no_grad()
        # DO NOT use torch.inference_mode()
        #
        # Grad-CAM needs the computation graph.
        # ----------------------------------------------------

        logits = self.model(
            input_tensor
        )


        # ----------------------------------------------------
        # Validate target class
        # ----------------------------------------------------

        if (
            target_index < 0
            or target_index >= logits.shape[1]
        ):

            raise ValueError(
                f"Invalid Grad-CAM target index "
                f"{target_index}. "
                f"Model has {logits.shape[1]} classes."
            )


        # ----------------------------------------------------
        # Target score
        # ----------------------------------------------------

        score = (
            logits[:, target_index]
            .sum()
        )


        # ----------------------------------------------------
        # Backward pass
        # ----------------------------------------------------

        score.backward()


        # ----------------------------------------------------
        # Validate hooks
        # ----------------------------------------------------

        if self.activations is None:

            raise RuntimeError(
                "Grad-CAM activation was not captured."
            )


        if self.gradients is None:

            raise RuntimeError(
                "Grad-CAM gradients were not captured."
            )


        # ----------------------------------------------------
        # Get activations and gradients
        # ----------------------------------------------------

        activations = (
            self.activations
            .detach()
        )

        gradients = (
            self.gradients
            .detach()
        )


        # ----------------------------------------------------
        # Global average pooling of gradients
        # ----------------------------------------------------

        weights = gradients.mean(
            dim=(2, 3),
            keepdim=True
        )


        # ----------------------------------------------------
        # Weighted activation map
        # ----------------------------------------------------

        cam = torch.relu(
            (
                weights
                * activations
            ).sum(
                dim=1,
                keepdim=True
            )
        )


        # ----------------------------------------------------
        # Resize CAM to original image
        # ----------------------------------------------------

        cam = torch.nn.functional.interpolate(

            cam,

            size=(
                image.height,
                image.width
            ),

            mode="bilinear",

            align_corners=False
        )


        # ----------------------------------------------------
        # Convert to NumPy
        # ----------------------------------------------------

        cam = (
            cam[0, 0]
            .cpu()
            .numpy()
        )


        # ----------------------------------------------------
        # Normalize CAM
        # ----------------------------------------------------

        cam -= cam.min()

        max_value = cam.max()

        if max_value > 0:

            cam /= max_value


        # ----------------------------------------------------
        # Create heatmap
        # ----------------------------------------------------

        heatmap = np.uint8(
            255 * cam
        )

        heatmap = cv2.applyColorMap(
            heatmap,
            cv2.COLORMAP_JET
        )


        # ----------------------------------------------------
        # Original image
        # ----------------------------------------------------

        original = cv2.cvtColor(

            np.array(
                image.convert("RGB")
            ),

            cv2.COLOR_RGB2BGR
        )


        # ----------------------------------------------------
        # Overlay
        # ----------------------------------------------------

        overlay = cv2.addWeighted(

            original,

            0.55,

            heatmap,

            0.45,

            0
        )


        # Convert BGR → RGB

        overlay = cv2.cvtColor(

            overlay,

            cv2.COLOR_BGR2RGB
        )


        # ----------------------------------------------------
        # Encode image as Base64
        # ----------------------------------------------------

        output = BytesIO()

        Image.fromarray(
            overlay
        ).save(
            output,
            format="JPEG",
            quality=90
        )


        return base64.b64encode(
            output.getvalue()
        ).decode("utf-8")


    # ========================================================
    # CLEANUP
    # ========================================================

    def close(self):

        if self.forward_handle is not None:

            self.forward_handle.remove()

            self.forward_handle = None


        if self.backward_handle is not None:

            self.backward_handle.remove()

            self.backward_handle = None


    # ========================================================
    # SAFETY CLEANUP
    # ========================================================

    def __del__(self):

        try:

            self.close()

        except Exception:

            pass